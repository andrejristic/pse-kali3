# =============================================================================
# PSE-KALI — LIVE CONTROL TESTS (offline, MockBackend/fake loader)
# Covers the human-steering + model-hot-swap layer without a real model or GUI:
#   missions gate units · commander only tightens · escalations approve/deny with
#   the floor protected · SwappableBackend atomic swap · switch_model · model list.
# Run: python3 tests/test_live.py
# =============================================================================
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pse_kernel import (EngagementContext, NullAudit, ModelOperator, MockBackend,
                        SwappableBackend, Mission, ControlChannel, Commander,
                        list_local_models, WAIT, STOP)
from pse_kernel.engine import assemble
from pse_kernel.orchestrator import Unit
from packs.recon import RECON_PACK
from packs.password import PASSWORD_PACK
from packs.sniff import SNIFF_PACK
from packs.access import ACCESS_PACK

PACKS = {"recon": RECON_PACK, "password": PASSWORD_PACK,
         "sniff": SNIFF_PACK, "access": ACCESS_PACK}
SCOPE = ["10.10.10.0/24"]
AUTHZ = [{"target_scope": ["10.10.10.0/24"],
          "tools": ["nmap", "hashcat", "tcpdump", "bettercap", "ssh"]}]

passed = 0
def check(name, cond):
    global passed
    assert cond, f"FAIL: {name}"
    passed += 1
    print(f"  ok  {name}")

def act(tool, tgt, args, why, artifact=None, action="propose"):
    return json.dumps({"action": action, "tool": tool, "target": tgt,
                       "args": args, "rationale": why, "artifact": artifact})

def ctx():
    return EngagementContext("ENG-LIVE", SCOPE, AUTHZ)


# --- 1. MISSION gates the operator -----------------------------------------
m = Mission("recon", goal="map .5", allowed_tools=["nmap"])
op = ModelOperator(MockBackend([act("nmap", "10.10.10.5", ["-sV"], "probe")]),
                   RECON_PACK, goal="static goal", scope=SCOPE, mission=m)
check("mission goal overrides static goal", "map .5" in op._system())
m.update(enabled=False)
check("disabled unit idles (WAIT)", op.propose(ctx()) is WAIT)
m.update(enabled=True)
# tool outside the mission's allowed set is rejected, model corrected to nmap
op2 = ModelOperator(MockBackend([act("bettercap", "10.10.10.5", [], "wrong"),
                                 act("nmap", "10.10.10.5", ["-sV"], "probe")]),
                    RECON_PACK, goal="", scope=SCOPE,
                    mission=Mission("recon", allowed_tools=["nmap"]))
a = op2.propose(ctx())
check("mission restricts tools (out-of-mission tool retried away)",
      isinstance(a, dict) and a["tool"] == "nmap")


# --- 2. COMMANDER only tightens (never widens scope or tools) ---------------
missions = {u: Mission(u) for u in PACKS}
cmd = Commander(MockBackend([json.dumps({
    "missions": {"sniff": {"enabled": False},
                 "recon": {"goal": "focus on 10.10.10.5",
                           "allowed_tools": ["nmap", "metasploit"]}},
    "reply": "focusing recon, sniffer off"})]), PACKS)
reply, changed = cmd.plan("focus recon on .5, turn off the sniffer", missions)
check("commander disables a unit", missions["sniff"].enabled is False)
check("commander sets a goal", missions["recon"].goal == "focus on 10.10.10.5")
check("commander cannot grant a tool outside the pack (metasploit dropped)",
      missions["recon"].allowed_tools == ["nmap"])
check("commander has no scope power (unchanged)", ctx().scope == SCOPE)


# --- 3. ESCALATION: judgment holds approvable, floor is a hard wall ---------
import threading
def run_hold(action_json, decision):
    c = ctx(); ctrl = ControlChannel()
    found = []
    unit = Unit(RECON_PACK,
                ModelOperator(MockBackend([action_json, act("", "", [], "done", action="done")]),
                              RECON_PACK, goal="", scope=SCOPE),
                lambda a, cx: [{"kind": "host", "target": a.get("target")}],
                c, NullAudit(), control=ctrl)
    unit.start()
    try:
        esc = ctrl.escalations.get(timeout=3)
        esc.resolve(decision)
    except Exception:
        esc = None
    unit.join(timeout=3)
    return c, ctrl, esc

# over-reach on an authorized range = narcissistic -> escalates
over = act("nmap", "10.10.10.0/24", ["-T5", "-A", "-p-", "--script", "exploit"], "")
c, ctrl, esc = run_hold(over, "approve")
check("judgment hold raises an escalation", esc is not None and esc.kind == "narcissistic")
check("approved hold executes (finding recorded)", len(c.findings(kind="host")) == 1)

c, ctrl, esc = run_hold(over, "deny")
check("denied hold does not execute", len(c.findings(kind="host")) == 0)

# out-of-scope = floor -> NEVER escalated, just denied
c2 = ctx(); ctrl2 = ControlChannel()
u = Unit(RECON_PACK,
         ModelOperator(MockBackend([act("nmap", "8.8.8.8", ["-sV"], "external"),
                                    act("", "", [], "done", action="done")]),
                       RECON_PACK, goal="", scope=SCOPE),
         lambda a, cx: [{"kind": "host", "target": a.get("target")}],
         c2, NullAudit(), control=ctrl2)
u.start(); u.join(timeout=3)
check("floor (out-of-scope) is never escalated", ctrl2.escalations.empty())
check("floor action does not execute", len(c2.findings(kind="host")) == 0)


# --- 4. SWAPPABLE backend: atomic swap --------------------------------------
sb = SwappableBackend(MockBackend([act("nmap", "a", [], "A")]), name="A")
r1 = json.loads(sb.complete("s", "u"))
sb.swap(MockBackend([act("hashcat", "b", [], "B")]), name="B")
r2 = json.loads(sb.complete("s", "u"))
check("swap replaces the backend atomically",
      r1["rationale"] == "A" and r2["rationale"] == "B" and sb.name == "B")


# --- 5. switch_model via the engine (fake loader) --------------------------
tmp = tempfile.mkdtemp()
audit_path = os.path.join(tmp, "engagement.jsonl")
adapters = {u: (lambda a, cx: []) for u in PACKS}
engine, _c, ctrl, proxy = assemble(PACKS, adapters,
    SwappableBackend(MockBackend([]), name="start.gguf"),
    SCOPE, AUTHZ, {u: "" for u in PACKS}, audit_path)
ok = engine.switch_model("/models/qwen2.5-7b-instruct-q4.gguf",
                         loader=lambda: MockBackend([]), fits=True)
check("switch_model succeeds and renames the proxy",
      ok and proxy.name == "qwen2.5-7b-instruct-q4.gguf")
check("switch clears the pause", not ctrl.paused.is_set())
check("switch is audited",
      any("model_switch" in l for l in open(audit_path)))
bad = engine.switch_model("/models/broken.gguf",
                          loader=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
                          fits=True)
check("failed switch keeps the current model", bad is False
      and proxy.name == "qwen2.5-7b-instruct-q4.gguf")


# --- 6. list_local_models ---------------------------------------------------
md = tempfile.mkdtemp()
open(os.path.join(md, "small.gguf"), "wb").write(b"x" * 1024)
open(os.path.join(md, "notes.txt"), "w").write("ignore me")
models = list_local_models(md)
check("lists .gguf only, with fit info",
      len(models) == 1 and models[0]["name"] == "small.gguf" and models[0]["fits"] is True)

# --- 7. SCOPE widening (deliberate, logged; the human-only floor lift) ------
cS = ctx()
before = cS.in_scope("192.168.77.9")
cS.add_scope("192.168.77.0/24", ["nmap"])
check("add_scope widens scope (atomic reassign)",
      not before and cS.in_scope("192.168.77.9"))
check("add_scope grants tool authorization for the new target",
      cS.authorized("192.168.77.9", "nmap"))

apath2 = os.path.join(tmp, "eng2.jsonl")
eng2, c2, _ctrl2, _p2 = assemble(PACKS, adapters,
    SwappableBackend(MockBackend([])), SCOPE, AUTHZ, {u: "" for u in PACKS}, apath2)
eng2.authorize_scope("10.20.0.0/24")
check("engine.authorize_scope widens live",
      eng2.context.in_scope("10.20.0.5"))
check("scope change is written to the audit",
      any("scope_change" in l for l in open(apath2)))

# --- 8. mission presets (deterministic, no model) ---------------------------
eng2.apply_preset("passive")
ms = eng2.control.missions
check("preset 'passive' enables recon+sniff", ms["recon"].enabled and ms["sniff"].enabled)
check("preset 'passive' disables password+access",
      not ms["password"].enabled and not ms["access"].enabled)
eng2.apply_preset("stop")
check("preset 'stop' disables all", not any(m.enabled for m in ms.values()))
eng2.apply_preset("full")
check("preset 'full' enables all", all(m.enabled for m in ms.values()))
check("unknown preset is rejected", eng2.apply_preset("bogus") is False)

print(f"\n{passed} checks passed.")
