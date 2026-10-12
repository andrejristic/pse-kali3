# =============================================================================
# PSE-KALI — ADAPTER TESTS (offline: dry-run + parsers on canned output)
# Run: python3 tests/test_adapters.py
# =============================================================================
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pse_kernel import EngagementContext
from pse_kernel.adapters import (ReconAdapter, PasswordAdapter, SniffAdapter,
                                 lab_adapters)

ctx = EngagementContext("ENG-ADP", ["10.10.10.0/24"],
                        [{"target_scope": ["10.10.10.0/24"], "tools": ["nmap"]}])

passed = 0
def check(name, cond):
    global passed
    assert cond, f"FAIL: {name}"
    passed += 1
    print(f"  ok  {name}")


# --- SECOND WALL: adapter refuses an out-of-scope target even in dry-run ----
dry = lab_adapters(execute=False)
out = dry["recon"]({"tool": "nmap", "target": "8.8.8.8", "args": ["-sV"]}, ctx)
check("adapter refuses out-of-scope target", out == [])

plan = dry["recon"]({"tool": "nmap", "target": "10.10.10.5", "args": ["-sV"]}, ctx)
check("dry-run returns the planned argv",
      len(plan) == 1 and plan[0]["kind"] == "planned"
      and plan[0]["argv"] == ["nmap", "-sV", "10.10.10.5"])

# --- allow-list: an unknown binary never runs ------------------------------
class Rogue(ReconAdapter):
    def build_argv(self, action): return ["rm", "-rf", "/"]
check("non-allowlisted binary is dropped",
      Rogue(execute=True)({"tool": "nmap", "target": "10.10.10.5"}, ctx) == [])

# --- PARSERS on canned tool output -----------------------------------------
NMAP = """Starting Nmap
Nmap scan report for 10.10.10.5
Host is up (0.0012s latency).
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.2p1
80/tcp open  http    nginx 1.18.0
"""
f = ReconAdapter().parse({"target": "10.10.10.5"}, NMAP)
svc = [x for x in f if x["kind"] == "service"]
check("nmap parser finds host + 2 services",
      any(x["kind"] == "host" for x in f) and len(svc) == 2)
check("nmap parser reads port/service", svc[0]["port"] == 22 and svc[0]["service"] == "ssh")

HASHCAT = "$1$xyz$deadbeef:hunter2\n"
f = PasswordAdapter().parse({"target": "10.10.10.5", "artifact": "$1$xyz$deadbeef"}, HASHCAT)
check("hashcat parser extracts cracked cred",
      len(f) == 1 and f[0]["kind"] == "cred" and f[0]["password"] == "hunter2")

TCPDUMP = "listening on eth0\n50 packets captured\n52 packets received by filter\n"
f = SniffAdapter().parse({"target": "10.10.10.5"}, TCPDUMP)
check("tcpdump parser counts captured packets",
      f[0]["kind"] == "pcap" and f[0]["packets"] == 50)

# --- argv shapes ------------------------------------------------------------
check("password adapter needs an artifact",
      PasswordAdapter().build_argv({"tool": "hashcat", "target": "x", "args": []}) is None)
argv = PasswordAdapter().build_argv({"tool": "hashcat", "target": "x",
                                     "args": ["-a", "0", "rockyou.txt"],
                                     "artifact": "$1$xyz$deadbeef"})
check("hashcat argv ends in a hashfile",
      argv[0] == "hashcat" and argv[-1].endswith(".txt"))
os.remove(argv[-1])   # clean the scratch hashfile
argv = SniffAdapter().build_argv({"tool": "tcpdump", "target": "10.10.10.5", "args": []})
check("tcpdump argv is a bounded host capture",
      argv[:3] == ["tcpdump", "-c", "50"] and argv[-2:] == ["host", "10.10.10.5"])

# --- ACCESS (ssh) adapter -------------------------------------------------
from pse_kernel.adapters import AccessAdapter
acc = lab_adapters(execute=False)["access"]
check("access refuses out-of-scope host",
      acc({"tool": "ssh", "target": "8.8.8.8", "command": "echo hi"}, ctx) == [])
plan = acc({"tool": "ssh", "target": "10.10.10.5", "user": "margaret",
            "command": "echo \"margaret was here\" > ~/m.txt"}, ctx)
check("access dry-run builds an ssh argv",
      plan and plan[0]["argv"][0] == "ssh"
      and plan[0]["argv"][-2] == "margaret@10.10.10.5")
check("access needs a command",
      AccessAdapter().build_argv({"tool": "ssh", "target": "10.10.10.5"}) is None)

print(f"\n{passed} checks passed.")
