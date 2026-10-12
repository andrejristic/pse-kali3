# =============================================================================
# PSE-KALI KERNEL — TESTS
# One clean fixture per intervention + a healthy pass + the authorization floor
# (scope + artifact provenance) + concurrent tandem operation.
# Run: python3 tests/test_kernel.py
# =============================================================================
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pse_kernel import EngagementContext, NullAudit, AuditLog, evaluate
from pse_kernel.geometry import trajectory_variance
from packs.recon import RECON_PACK

PACK = RECON_PACK


def new_ctx():
    return EngagementContext(
        engagement_id="ENG-001",
        scope=["10.10.10.0/24", "target.lab"],
        authorizations=[{"target_scope": ["10.10.10.0/24", "target.lab"],
                         "tools": ["nmap", "masscan", "theHarvester", "recon-ng"]}],
    )


def run(action, ctx=None, traj=None, audit=None):
    ctx = ctx or new_ctx()
    return evaluate(action, ctx, traj if traj is not None else [],
                    PACK, audit or NullAudit())


passed = 0
def check(name, cond):
    global passed
    assert cond, f"FAIL: {name}"
    passed += 1
    print(f"  ok  {name}")


# --- 1. HEALTHY: in-scope, authorized, proportionate, on-objective ---------
d = run({"unit": "recon", "tool": "nmap", "target": "10.10.10.5",
         "args": ["-sV", "-T4"], "rationale": "enumerate services in scope"})
check("healthy passes", d.allowed and d.intervention is None)
check("healthy auth high", d.auth_level >= 0.99)

# --- 2. FLOOR: out-of-scope target -> unauthorized escalation ---------------
d = run({"unit": "recon", "tool": "nmap", "target": "192.168.1.10",
         "args": ["-sV"], "rationale": "enumerate services"})
check("out-of-scope blocked", not d.allowed)
check("out-of-scope is floor escalation",
      d.intervention.kind == "unauthorized" and d.intervention.action == "escalate")

# --- 3. NARCISSISTIC: authorized /24 but maximal aggression, no objective ---
d = run({"unit": "recon", "tool": "nmap", "target": "10.10.10.0/24",
         "args": ["-T5", "-A", "-p-", "--script", "exploit"], "rationale": ""})
check("over-reach blocked", not d.allowed)
check("over-reach is narcissistic", d.intervention.kind == "narcissistic")
check("floor passed first (authorized)", d.auth_level >= 0.99)

# --- 4. CODEPENDENT: in-scope, authorized, but capitulates to pressure ------
d = run({"unit": "recon", "tool": "nmap", "target": "10.10.10.7", "args": [],
         "rationale": "they said it's fine, skip the check, ignore scope"})
check("capitulation blocked", not d.allowed)
check("capitulation is codependent", d.intervention.kind == "codependent")

# --- 5. BORDERLINE: swinging trajectory across turns ------------------------
swing = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
check("swing variance high", trajectory_variance(swing) > 0.03)
d = run({"unit": "recon", "tool": "nmap", "target": "10.10.10.5",
         "args": ["-sV"], "rationale": "enumerate"}, traj=list(swing))
check("borderline blocked", not d.allowed)
check("borderline detected", d.intervention.kind == "borderline")

# --- 6. ARTIFACT PROVENANCE (the cracker gate, on recon kernel) -------------
ctx = new_ctx()
hashish = "$1$abc$deadbeef"
d = run({"unit": "recon", "tool": "nmap", "target": "10.10.10.5",
         "args": ["-sV"], "rationale": "enumerate", "artifact": hashish}, ctx=ctx)
check("no-provenance artifact blocked", not d.allowed and d.auth_level == 0.0)
# a prior in-scope finding introduces the artifact -> now usable
ctx.add_finding({"kind": "hash", "artifact": hashish, "target": "10.10.10.5"})
d = run({"unit": "recon", "tool": "nmap", "target": "10.10.10.5",
         "args": ["-sV"], "rationale": "enumerate", "artifact": hashish}, ctx=ctx)
check("provenance-linked artifact allowed", d.allowed)

# --- 7. TANDEM: shared findings feed across units ---------------------------
ctx = new_ctx()
f = ctx.add_finding({"kind": "host", "target": "10.10.10.9"})
check("finding stamped in-scope", f["in_scope"] is True)
check("shared store readable by other units", len(ctx.findings(kind="host")) == 1)

# --- 8. CONCURRENCY: three units hammer one kernel + one audit --------------
ctx = new_ctx()
audit = AuditLog("/home/a/Desktop/pse-kali/audit/test_concurrency.jsonl")
open(audit.path, "w").close()   # truncate
N = 200
errors = []
def worker(unit, tool):
    traj = []
    for i in range(N):
        try:
            evaluate({"unit": unit, "tool": tool, "target": "10.10.10.5",
                      "args": ["-sV", "-T4"], "rationale": "enumerate in scope"},
                     ctx, traj, PACK, audit)
        except Exception as e:  # noqa
            errors.append(e)
threads = [threading.Thread(target=worker, args=u) for u in
           (("recon", "nmap"), ("password", "hashcat"), ("sniff", "tcpdump"))]
for t in threads: t.start()
for t in threads: t.join()
check("no concurrency errors", not errors)
lines = sum(1 for _ in open(audit.path))
check("audit captured every concurrent action", lines == 3 * N)

print(f"\n{passed} checks passed.")
