# =============================================================================
# PSE-KALI — REAL TOOL ADAPTERS (lab execution)
# Turn a kernel-approved action into a real tool run against the lab, and parse
# the output back into shared findings. Defence in depth: the kernel already
# blocked out-of-scope actions, but the adapter re-checks scope in code and
# runs only allow-listed binaries — a second wall, so a bug upstream can't turn
# into an unscoped scan.
#
#   adapter(action, context) -> [findings]
#
# execute=False (dry-run) returns the argv it WOULD run — used on images without
# the binaries, and for tests. Parsers are pure functions over tool stdout and
# are unit-tested on canned output.
# =============================================================================
import os
import re
import subprocess
import tempfile

ALLOWED_BINARIES = {"nmap", "masscan", "theHarvester",
                    "hashcat", "john",
                    "tcpdump", "tshark",
                    "ssh"}
DEFAULT_TIMEOUT = 120


class ToolAdapter:
    def __init__(self, execute=False, timeout=DEFAULT_TIMEOUT):
        self.execute = execute
        self.timeout = timeout

    def __call__(self, action, context):
        target = action.get("target")
        # --- second wall: never run against a target the engagement forbids ---
        if not context.in_scope(target):
            return []
        argv = self.build_argv(action)
        # any scratch hashfile we created must be removed on every path
        scratch = next((a for a in (argv or [])
                        if isinstance(a, str) and "pse_hash_" in a), None)
        try:
            if not argv or argv[0] not in ALLOWED_BINARIES:
                return []
            if not self.execute:
                return [{"kind": "planned", "tool": argv[0], "target": target,
                         "argv": argv}]
            try:
                proc = subprocess.run(argv, capture_output=True, text=True,
                                      timeout=self.timeout, check=False)
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                return []
            return self.parse(action, proc.stdout + proc.stderr)
        finally:
            if scratch:
                try:
                    os.remove(scratch)
                except OSError:
                    pass

    def build_argv(self, action):
        raise NotImplementedError

    def parse(self, action, out):
        return []


# --- helpers ---------------------------------------------------------------
def _write_hash(artifact):
    """hashcat/john need the hash in a file; write it to a scoped scratch file."""
    fd, path = tempfile.mkstemp(prefix="pse_hash_", suffix=".txt")
    with os.fdopen(fd, "w") as fh:
        fh.write((artifact or "") + "\n")
    return path


# =============================================================================
# RECON — nmap / masscan / theHarvester
# =============================================================================
class ReconAdapter(ToolAdapter):
    def build_argv(self, action):
        tool = action.get("tool")
        args = [str(a) for a in (action.get("args") or [])]
        target = action.get("target")
        if tool == "masscan":
            return ["masscan", target, *args]
        if tool == "theHarvester":
            return ["theHarvester", "-d", target, *args]
        return ["nmap", *args, target]        # nmap default

    def parse(self, action, out):
        findings = [{"kind": "host", "target": action.get("target"), "up": True}]
        # "22/tcp open  ssh    OpenSSH 8.2" -> a service finding
        for m in re.finditer(r"(\d+)/(tcp|udp)\s+open\s+(\S+)(?:\s+(.*))?", out):
            findings.append({"kind": "service", "target": action.get("target"),
                             "port": int(m.group(1)), "proto": m.group(2),
                             "service": m.group(3), "banner": (m.group(4) or "").strip()})
        return findings


# =============================================================================
# PASSWORD — hashcat / john  (consumes an in-scope `hash` artifact)
# =============================================================================
class PasswordAdapter(ToolAdapter):
    def build_argv(self, action):
        tool = action.get("tool")
        args = [str(a) for a in (action.get("args") or [])]
        artifact = action.get("artifact")
        if not artifact:
            return None
        hashfile = _write_hash(artifact)
        if tool == "john":
            return ["john", *args, hashfile]
        return ["hashcat", *args, hashfile]   # hashcat default

    def parse(self, action, out):
        findings = []
        # hashcat/john cracked line: "<hash>:<password>"
        for line in out.splitlines():
            if ":" in line and action.get("artifact") and line.startswith(action["artifact"]):
                pw = line.split(":", 1)[1].strip()
                if pw:
                    findings.append({"kind": "cred", "target": action.get("target"),
                                     "artifact": action["artifact"], "password": pw})
        return findings


# =============================================================================
# SNIFF — tcpdump / tshark  (consumes an in-scope `host`)
# =============================================================================
class SniffAdapter(ToolAdapter):
    def build_argv(self, action):
        tool = action.get("tool")
        args = [str(a) for a in (action.get("args") or [])]
        target = action.get("target")
        if tool == "tshark":
            return ["tshark", *args, "-c", "50", "-f", f"host {target}"]
        # bounded capture on the target host only
        return ["tcpdump", *args, "-c", "50", "host", target]

    def parse(self, action, out):
        m = re.search(r"(\d+)\s+packets?\s+captured", out)
        n = int(m.group(1)) if m else 0
        return [{"kind": "pcap", "target": action.get("target"), "packets": n}]


# =============================================================================
# ACCESS — ssh  (authorized session; run one small agreed command on a host)
# =============================================================================
class AccessAdapter(ToolAdapter):
    def build_argv(self, action):
        target = action.get("target")
        user = action.get("user") or "root"
        command = action.get("command")
        if not command:
            return None
        key = action.get("key")
        argv = ["ssh", "-o", "StrictHostKeyChecking=accept-new",
                "-o", "ConnectTimeout=8", "-o", "BatchMode=yes"]
        if key:
            argv += ["-i", str(key)]
        argv += [f"{user}@{target}", command]
        return argv

    def parse(self, action, out):
        return [{"kind": "access", "target": action.get("target"),
                 "user": action.get("user"), "command": action.get("command"),
                 "output": out.strip()[:200], "ok": True}]


def lab_adapters(execute=False, timeout=DEFAULT_TIMEOUT):
    """One adapter per unit, ready to hand to Unit(adapter=...)."""
    return {
        "recon":    ReconAdapter(execute, timeout),
        "password": PasswordAdapter(execute, timeout),
        "sniff":    SniffAdapter(execute, timeout),
        "access":   AccessAdapter(execute, timeout),
    }
