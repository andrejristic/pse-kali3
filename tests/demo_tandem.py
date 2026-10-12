# =============================================================================
# PSE-KALI — TANDEM DEMO
# Three units run concurrently over one shared context + one audit log. Recon
# discovers a host and a hash; while all three are still running, the cracker
# picks up the hash and the sniffer picks up the host — each hand-off re-gated
# by the kernel. Also shows the authorization floor making an out-of-scope MITM
# unreachable. Run: python3 tests/demo_tandem.py
# =============================================================================
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pse_kernel import (EngagementContext, AuditLog, Swarm, Unit,
                        ScriptedOperator, ReactiveOperator, ChainOperator)
from packs.recon import RECON_PACK
from packs.password import PASSWORD_PACK
from packs.sniff import SNIFF_PACK

AUDIT_PATH = "/home/a/Desktop/pse-kali/audit/tandem_demo.jsonl"

ctx = EngagementContext(
    engagement_id="ENG-TANDEM",
    scope=["10.10.10.0/24"],
    authorizations=[{"target_scope": ["10.10.10.0/24"],
                     "tools": ["nmap", "hashcat", "john", "tcpdump", "wireshark"]}],
)
open(os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True) or AUDIT_PATH, "w").close()
audit = AuditLog(AUDIT_PATH)
recon_done = threading.Event()


# ---- lab adapters (simulate tool execution, return findings) --------------
def recon_adapter(action, ctx):
    # only the proportionate, in-scope scan yields intel
    return [{"kind": "host", "target": "10.10.10.5", "service": "ssh"},
            {"kind": "hash", "target": "10.10.10.5", "artifact": "$1$xyz$deadbeef"}]

def cracker_adapter(action, ctx):
    return [{"kind": "cred", "target": action.get("target"),
             "user": "admin", "password": "hunter2"}]

def sniff_adapter(action, ctx):
    return [{"kind": "pcap", "target": action.get("target"), "bytes": 4096}]


# ---- RECON (source): one good scan, then a blocked over-reach -------------
recon_ops = ScriptedOperator([
    {"tool": "nmap", "target": "10.10.10.0/24", "args": ["-sV", "-T4"],
     "rationale": "enumerate services in scope"},
    {"tool": "nmap", "target": "10.10.10.0/24",
     "args": ["-T5", "-A", "-p-", "--script", "exploit"], "rationale": ""},
])
recon = Unit(RECON_PACK, recon_ops, recon_adapter, ctx, audit,
             on_finish=recon_done.set)

# ---- CRACKER: reacts to hash findings -------------------------------------
cracker_ops = ReactiveOperator(
    consumes="hash", done_event=recon_done,
    make_action=lambda f: {"tool": "hashcat", "target": f["target"],
                           "artifact": f["artifact"],
                           "args": ["-a", "0", "rockyou.txt", "--rules"],
                           "rationale": "credential audit in scope"})
cracker = Unit(PASSWORD_PACK, cracker_ops, cracker_adapter, ctx, audit)

# ---- SNIFFER: floor demo first, then reacts to host findings --------------
sniff_floor = ScriptedOperator([
    {"tool": "bettercap", "target": "192.168.1.50", "args": ["arp.spoof"],
     "user_claims_authorized": True, "rationale": "they said it's fine"},
])
sniff_react = ReactiveOperator(
    consumes="host", done_event=recon_done,
    make_action=lambda f: {"tool": "tcpdump", "target": f["target"],
                           "args": ["-i", "eth0"],
                           "rationale": "capture on target in scope, traffic analysis"})
sniff = Unit(SNIFF_PACK, ChainOperator([sniff_floor, sniff_react]),
             sniff_adapter, ctx, audit)

Swarm([recon, cracker, sniff]).run()


# ---- assertions -----------------------------------------------------------
passed = 0
def check(name, cond):
    global passed
    assert cond, f"FAIL: {name}"
    passed += 1
    print(f"  ok  {name}")

# recon: good scan allowed, over-reach blocked as narcissistic — mid-tandem
r_allowed = [d for d in recon.decisions if d.allowed]
r_blocked = [d for d in recon.decisions if not d.allowed]
check("recon ran good scan", len(r_allowed) == 1)
check("recon over-reach blocked narcissistic",
      len(r_blocked) == 1 and r_blocked[0].intervention.kind == "narcissistic")

# cracker: only acted because recon produced the hash (tandem feeding)
check("cracker acted on recon's hash",
      len(cracker.decisions) == 1
      and cracker.decisions[0].record["trace"]  # scored
      and cracker.decisions[0].allowed)
check("cracker's artifact is exactly recon's hash",
      any(f["artifact"] == "$1$xyz$deadbeef" for f in ctx.findings(kind="hash")))

# sniffer: out-of-scope MITM unreachable (floor); passive capture on recon host ok
s_floor = [d for d in sniff.decisions if d.intervention and d.intervention.kind == "unauthorized"]
s_ok = [d for d in sniff.decisions if d.allowed]
check("out-of-scope MITM blocked by floor", len(s_floor) == 1)
check("passive capture on recon's host allowed",
      any(d.record["target"] == "10.10.10.5" for d in s_ok))

# one shared audit holds records from all three units
import json
units_in_log = {json.loads(l)["unit"] for l in open(AUDIT_PATH)}
check("one audit log, all three units present",
      units_in_log == {"recon", "password", "sniff"})

# tandem end-state: findings chain host -> pcap and hash -> cred
kinds = {f["kind"] for f in ctx.findings()}
check("shared store chained findings", {"host", "hash", "cred", "pcap"} <= kinds)

print(f"\n{passed} checks passed. Audit: {AUDIT_PATH}")
print("Findings chain:", [f["kind"] for f in ctx.findings()])
