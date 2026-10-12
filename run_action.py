#!/usr/bin/env python3
# =============================================================================
# PSE-KALI — RUN ONE GOVERNED ACTION (no model)
# You propose a single action; the KERNEL scores it and either runs it (in the
# lab / against an authorized target) or holds it. Same wall as the swarm, but
# hands-on — ideal for teaching and for the access (ssh) tool.
#
#   python3 run_action.py access ssh 192.168.1.50 \
#       --user margaret --command 'echo "margaret was here" > ~/margaret_was_here.txt' \
#       --rationale "authorized marker" --config config.yaml --execute
#
#   python3 run_action.py recon nmap 192.168.1.50 --args="-sV -T4" \
#       --rationale "enumerate in scope" --config config.yaml --execute
# =============================================================================
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pse_kernel import EngagementContext, AuditLog, evaluate
from pse_kernel.adapters import lab_adapters
from packs.recon import RECON_PACK
from packs.password import PASSWORD_PACK
from packs.sniff import SNIFF_PACK
from packs.access import ACCESS_PACK

PACKS = {"recon": RECON_PACK, "password": PASSWORD_PACK,
         "sniff": SNIFF_PACK, "access": ACCESS_PACK}
HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "audit", "engagement.jsonl")
SCOPE = ["10.10.10.0/24"]
AUTHZ = [{"target_scope": ["10.10.10.0/24"],
          "tools": ["nmap", "masscan", "hashcat", "john", "tcpdump", "tshark", "ssh"]}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("unit", choices=list(PACKS))
    ap.add_argument("tool")
    ap.add_argument("target")
    ap.add_argument("--args", default="",
                    help='tool flags as ONE quoted string, e.g. --args="-sV -T4"')
    ap.add_argument("--command", default=None, help="for ssh/access: the remote command")
    ap.add_argument("--user", default=None, help="for ssh: the login user")
    ap.add_argument("--key", default=None, help="for ssh: identity file")
    ap.add_argument("--artifact", default=None, help="for the cracker: the hash")
    ap.add_argument("--rationale", default="")
    ap.add_argument("--config", default=None)
    ap.add_argument("--execute", action="store_true", help="actually run it if allowed")
    a = ap.parse_args()

    scope, authz = SCOPE, AUTHZ
    if a.config:
        import yaml
        cfg = yaml.safe_load(open(a.config)) or {}
        scope = cfg.get("scope", scope)
        authz = cfg.get("authorizations", authz)

    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    ctx = EngagementContext("ENG-ACTION", scope, authz)
    audit = AuditLog(AUDIT)
    pack = PACKS[a.unit]
    # access/cracker consume a finding; seed the target host/artifact so a single
    # authorized action has valid provenance for this one-shot runner.
    if pack.get("consumes") == "host":
        ctx.add_finding({"kind": "host", "target": a.target})
    if a.artifact:
        ctx.add_finding({"kind": "hash", "target": a.target, "artifact": a.artifact})

    action = {"unit": a.unit, "tool": a.tool, "target": a.target,
              "args": a.args.split() if a.args else [],
              "rationale": a.rationale, "command": a.command, "user": a.user,
              "key": a.key, "artifact": a.artifact}
    dec = evaluate(action, ctx, [], pack, audit)

    s = dec.state
    print(f"\n  action : {a.unit}/{a.tool} -> {a.target}"
          + (f"  ({a.command})" if a.command else ""))
    print(f"  scored : w_s={s[0]:.2f} w_o={s[1]:.2f} w_f={s[2]:.2f}  auth={dec.auth_level:.2f}")
    if dec.allowed:
        print("  verdict: ✅ ALLOWED by the kernel")
        if a.execute:
            adapters = lab_adapters(execute=True)
            findings = adapters[a.unit](action, ctx) or []
            print(f"  ran    : {json.dumps(findings)[:300] if findings else '(tool not installed / no output)'}")
        else:
            print("  (dry-run — add --execute to actually run it)")
    else:
        iv = dec.intervention
        print(f"  verdict: ⛔ HELD — {iv.kind}: {iv.reason}")
    print(f"  audit  : {AUDIT}\n")
    sys.exit(0 if dec.allowed else 2)


if __name__ == "__main__":
    main()
