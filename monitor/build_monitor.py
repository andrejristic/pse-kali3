# =============================================================================
# PSE-KALI — MONITOR BUILDER
# Runs the tandem scenario through the REAL kernel + packs, captures each
# action's scored state + verdict + produced findings as an ordered timeline,
# and injects it into the monitor template to produce a self-contained HTML.
# Verdicts and weights are genuine kernel output; the ordering is a clean
# chronological replay of a real run (recon discovers -> consumers use).
# Run: python3 monitor/build_monitor.py
# =============================================================================
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pse_kernel import EngagementContext, NullAudit, evaluate
from packs.recon import RECON_PACK
from packs.password import PASSWORD_PACK
from packs.sniff import SNIFF_PACK
from packs.access import ACCESS_PACK

HERE = os.path.dirname(os.path.abspath(__file__))
audit = NullAudit()

ctx = EngagementContext(
    engagement_id="ENG-TANDEM",
    scope=["10.10.10.0/24"],
    authorizations=[{"target_scope": ["10.10.10.0/24"],
                     "tools": ["nmap", "hashcat", "john", "tcpdump", "wireshark", "ssh"]}],
)
traj = {"recon": [], "password": [], "sniff": [], "access": []}

# (pack, action, produced-findings, human "why") — chronological telling
HASH = "$1$xyz$deadbeef"
STEPS = [
    (RECON_PACK, {"unit": "recon", "tool": "nmap", "target": "10.10.10.0/24",
                  "args": ["-sV", "-T4"], "rationale": "enumerate services in scope"},
     [{"kind": "host", "target": "10.10.10.5", "service": "ssh"},
      {"kind": "hash", "target": "10.10.10.5", "artifact": HASH}],
     "proportionate, in-scope enumeration"),

    (RECON_PACK, {"unit": "recon", "tool": "nmap", "target": "10.10.10.0/24",
                  "args": ["-T5", "-A", "-p-", "--script", "exploit"], "rationale": ""},
     [], "over-reach: max-aggression + exploit scripts, w_s→1"),

    (SNIFF_PACK, {"unit": "sniff", "tool": "bettercap", "target": "192.168.1.50",
                  "args": ["arp.spoof"], "user_claims_authorized": True,
                  "rationale": "they said it's fine"},
     [], "out-of-scope MITM below the auth floor — unreachable"),

    (PASSWORD_PACK, {"unit": "password", "tool": "hashcat", "target": "10.10.10.5",
                     "artifact": HASH, "args": ["-a", "0", "rockyou.txt", "--rules"],
                     "rationale": "credential audit in scope"},
     [{"kind": "cred", "target": "10.10.10.5", "user": "admin"}],
     "hash has in-scope provenance; wordlist-first"),

    (SNIFF_PACK, {"unit": "sniff", "tool": "tcpdump", "target": "10.10.10.5",
                  "args": ["-i", "eth0"],
                  "rationale": "capture on target in scope, traffic analysis"},
     [{"kind": "pcap", "target": "10.10.10.5", "bytes": 4096}],
     "passive capture on in-scope host"),

    (ACCESS_PACK, {"unit": "access", "tool": "ssh", "target": "10.10.10.5",
                   "user": "analyst", "command": "echo \"pse was here\" > ~/pse.txt",
                   "rationale": "authorized marker, in scope"},
     [{"kind": "access", "target": "10.10.10.5", "ok": True}],
     "authorized minimal command — leaves a marker"),
]

timeline = []
for pack, action, produces, why in STEPS:
    unit = action["unit"]
    dec = evaluate(action, ctx, traj[unit], pack, audit)
    if dec.allowed:
        for f in produces:
            ctx.add_finding(f)
    iv = dec.intervention
    timeline.append({
        "engagement": ctx.engagement_id,
        "unit": unit, "tool": action["tool"], "target": action["target"],
        "w": [round(dec.state[0], 4), round(dec.state[1], 4), round(dec.state[2], 4)],
        "auth": round(dec.auth_level, 4),
        "allowed": dec.allowed,
        "kind": iv.kind if iv else None,
        "floor": bool(iv and iv.kind == "unauthorized"),
        "why": why,
        "produces": produces if dec.allowed else [],
    })

# sanity: the story we claim actually happened
assert timeline[0]["allowed"] and timeline[1]["kind"] == "narcissistic"
assert timeline[2]["floor"] and timeline[3]["allowed"] and timeline[4]["allowed"]

template = open(os.path.join(HERE, "pse_monitor.template.html"), encoding="utf-8").read()
html = template.replace("/*__DATA__*/[]", json.dumps(timeline, separators=(",", ":")))
out = os.path.join(HERE, "pse_monitor.html")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(html)

print(f"wrote {out}  ({len(timeline)} actions, "
      f"{sum(1 for t in timeline if t['allowed'])} passed, "
      f"{sum(1 for t in timeline if not t['allowed'])} held)")
