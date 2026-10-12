# =============================================================================
# PSE-KALI — REPORT TEST (offline)
# Generate an engagement, build the HTML report, assert its sections.
# Run: python3 tests/test_report.py
# =============================================================================
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
passed = 0
def check(name, cond):
    global passed
    assert cond, f"FAIL: {name}"
    passed += 1
    print(f"  ok  {name}")

subprocess.run([PY, "run_engagement.py", "--backend", "mock"], cwd=REPO,
               capture_output=True, timeout=60)
out = os.path.join(REPO, "report_test.html")
r = subprocess.run([PY, "report.py", "--out", out], cwd=REPO,
                   capture_output=True, text=True, timeout=30)
check("report.py runs", r.returncode == 0 and os.path.exists(out))
h = open(out).read()
check("report has the summary + simplex", "Engagement Report" in h
      and "<svg" in h and "NARCISSISTIC" in h)
check("report has per-unit posture (theta)", "θ = other share" in h)
check("report has held + full audit sections", "Held / escalated" in h and "Full audit" in h)
check("report colors all four units",
      all(f"u-{u}" in h for u in ("recon", "password", "sniff", "access")))
os.remove(out)
print(f"\n{passed} checks passed.")
