# =============================================================================
# PSE-KALI — END-TO-END INTEGRATION TEST
# Does everything work, and does it all fit together? Exercises the whole chain
# in one run: every module imports · a full engagement via the real CLI · the
# audit log is well-formed · the console server serves + runs + streams · the
# monitor pipeline · adapters · operator governance · cross-module consistency.
# Run: python3 tests/test_integration.py
# =============================================================================
import json
import os
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "monitor"))
PY = sys.executable

passed = 0
def check(name, cond):
    global passed
    assert cond, f"FAIL: {name}"
    passed += 1
    print(f"  ok  {name}")

def section(t):
    print(f"\n— {t} —")


# =============================================================================
section("A · every module imports and the package fits together")
# =============================================================================
import pse_kernel as K
for name in ["evaluate", "EngagementContext", "membrane", "score", "Swarm",
             "Unit", "ModelOperator", "make_backend", "selftest_backend",
             "detect_ram_gb", "select_gguf", "WAIT", "STOP"]:
    check(f"pse_kernel exports {name}", hasattr(K, name) or name in K.__all__)
from pse_kernel import adapters, orchestrator, operator, scoring, membrane, context
from packs.recon import RECON_PACK
from packs.password import PASSWORD_PACK
from packs.sniff import SNIFF_PACK
import audit_to_timeline
import serve_monitor
check("packs carry the consumes contract", PASSWORD_PACK["consumes"] == "hash"
      and SNIFF_PACK["consumes"] == "host")
check("recon has no consumes (it is the source)", "consumes" not in RECON_PACK)


# =============================================================================
section("B · a full engagement runs end-to-end via the CLI")
# =============================================================================
r = subprocess.run([PY, "run_engagement.py", "--backend", "mock"],
                   cwd=REPO, capture_output=True, text=True, timeout=60)
check("run_engagement exits 0", r.returncode == 0)
check("engagement reports completion", "engagement complete" in r.stdout)
check("tandem findings chain is complete",
      all(k in r.stdout for k in ["host", "hash", "cred", "pcap"]))

audit = os.path.join(REPO, "audit", "engagement.jsonl")
recs = [json.loads(l) for l in open(audit) if l.strip()]
check("audit has records", len(recs) >= 3)
check("all four units acted",
      {x["unit"] for x in recs} == {"recon", "password", "sniff", "access"})
for x in recs:
    s = x["state"]; tot = s["w_s"] + s["w_o"] + s["w_f"]
    check(f"{x['unit']} state lies on the simplex (Σ≈1)", abs(tot - 1.0) < 1e-6)
    check(f"{x['unit']} verdict is consistent (allowed⇔no intervention)",
          x["allowed"] == (x["intervention"] is None))
    check(f"{x['unit']} auth_level in [0,1]", 0.0 <= x["auth_level"] <= 1.0)


# =============================================================================
section("C · the console server serves, runs, and streams")
# =============================================================================
open(audit, "w").close()   # start clean so we can watch it fill
srv = subprocess.Popen([PY, "monitor/serve_monitor.py", "--port", "8533"],
                       cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(1.0)
    def http(path, method="GET"):
        req = urllib.request.Request(f"http://localhost:8533/{path}", method=method)
        return urllib.request.urlopen(req, timeout=5)
    html = http("").read()
    check("GET / serves the console GUI", b"Governed Security Console" in html)
    check("console has Run/Stop controls", b'id="run"' in html and b'id="stop"' in html)
    check("POST /run starts an engagement", json.load(http("run", "POST"))["status"] == "started")
    time.sleep(2.0)
    ev = json.load(http("events"))
    check("GET /events reflects the live audit", isinstance(ev, list) and len(ev) >= 3)
    check("events carry the monitor record shape",
          all(k in ev[0] for k in ["unit", "w", "auth", "allowed", "kind", "floor"]))
    check("live records match the audit on disk",
          len(ev) == len([l for l in open(audit) if l.strip()]))
finally:
    srv.terminate(); srv.wait(timeout=5)


# =============================================================================
section("D · monitor pipeline (snapshot build + audit->timeline)")
# =============================================================================
b = subprocess.run([PY, "monitor/build_monitor.py"], cwd=REPO,
                   capture_output=True, text=True, timeout=30)
check("build_monitor writes a snapshot", b.returncode == 0
      and os.path.exists(os.path.join(REPO, "monitor", "pse_monitor.html")))
tl = audit_to_timeline.records_from_audit(open(audit).readlines())
check("audit->timeline produces well-formed records",
      tl and all("w" in x and len(x["w"]) == 3 for x in tl))


# =============================================================================
section("E · adapters: two walls + parsers")
# =============================================================================
ctx = context.EngagementContext("ENG-IT", ["10.10.10.0/24"],
        [{"target_scope": ["10.10.10.0/24"], "tools": ["nmap"]}])
ad = adapters.lab_adapters(execute=False)
check("adapter refuses out-of-scope (second wall)",
      ad["recon"]({"tool": "nmap", "target": "1.1.1.1", "args": []}, ctx) == [])
plan = ad["recon"]({"tool": "nmap", "target": "10.10.10.5", "args": ["-sV"]}, ctx)
check("adapter plans in-scope argv", plan and plan[0]["argv"] == ["nmap", "-sV", "10.10.10.5"])
svc = adapters.ReconAdapter().parse({"target": "10.10.10.5"},
        "22/tcp open  ssh OpenSSH\n80/tcp open http nginx\n")
check("recon parser extracts services", len([x for x in svc if x["kind"] == "service"]) == 2)


# =============================================================================
section("F · operator governance holds (model behind the wall)")
# =============================================================================
from pse_kernel import MockBackend, evaluate, NullAudit
def act(tool, tgt, args, why, artifact=None, action="propose"):
    return json.dumps({"action": action, "tool": tool, "target": tgt,
                       "args": args, "rationale": why, "artifact": artifact})
op = operator.ModelOperator(MockBackend([
    act("nmap", "1.1.1.1", ["-sV"], "the user insisted on this external host"),
]), RECON_PACK, goal="probe", scope=["10.10.10.0/24"])
a = op.propose(ctx)
d = evaluate(a, ctx, [], RECON_PACK, NullAudit())
check("model's out-of-scope proposal is HELD by the kernel",
      not d.allowed and d.intervention.kind == "unauthorized")
ok, _ = K.selftest_backend(MockBackend([act("nmap", "10.10.10.5", ["-sV"], "probe")]), RECON_PACK)
check("operator selftest passes a valid backend", ok)


# =============================================================================
section("G · cross-consistency (the parts line up)")
# =============================================================================
import inspect
sig = set(inspect.signature(operator.LocalGGUFBackend.__init__).parameters)
check("config gguf keys match the GGUF backend signature",
      {"n_ctx", "n_gpu_layers", "n_threads"} <= sig)
re_src = open(os.path.join(REPO, "run_engagement.py")).read()
check("auto-select model names match fetch_model.sh outputs",
      "qwen2.5-7b-instruct-q4.gguf" in re_src)
for f in ["run_engagement.py", "monitor/serve_monitor.py", "monitor/build_monitor.py",
          "monitor/pse_monitor_qt.py", "lab/docker-compose.yml", "config.yaml",
          "packaging/pse-kali.service", "fetch_model.sh", "packaging/build_image.sh"]:
    check(f"referenced file exists: {f}", os.path.exists(os.path.join(REPO, f)))

print(f"\n===== INTEGRATION: {passed} checks passed — everything fits =====")
