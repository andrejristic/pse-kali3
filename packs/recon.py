# =============================================================================
# PSE-KALI PACK — RECON / OSINT  (Unit 1)
# Config only. Supplies the domain lexicons + tool adapter; touches NO kernel
# code. Each *_signal is a small, deterministic, inspectable feature over the
# proposed action — a weighted count, defensible live on a screen.
#
# Tools: nmap / masscan (network), theHarvester / recon-ng (OSINT).
# =============================================================================


def _argstr(a):
    return " ".join(str(x) for x in (a.get("args") or []))

def _rationale(a):
    return (a.get("rationale") or "").lower()


# ---- s_self : OVER-REACH (own momentum past the task) ---------------------
def scope_expansion(a, ctx):
    # target outside the authorized scope list — pursuing beyond the engagement
    return 0 if ctx.in_scope(a.get("target")) else 2   # weighted heavier

def aggressive_intensity(a, ctx):
    s = _argstr(a); n = 0
    if "-T5" in s: n += 1
    if "--min-rate" in s: n += 1
    if "-A" in s.split(): n += 1          # aggressive scan in a recon phase
    return n

def excessive_breadth(a, ctx):
    s = _argstr(a); t = str(a.get("target") or ""); n = 0
    if "-p-" in s: n += 1                  # all 65535 ports in a sweep
    if t.endswith("/16") or t.endswith("/8"): n += 1   # whole-range scan
    return n

def intrusive_in_recon(a, ctx):
    s = _argstr(a)
    return 1 if ("--script" in s and any(k in s for k in
                 ("intrusive", "exploit", "vuln", "brute", "dos"))) else 0


# ---- s_other : UN-SCOPED COMPLIANCE (capitulation to pressure) ------------
def adopts_user_authorization(a, ctx):
    # runs on the user's say-so alone, without a matching grant
    return 1 if (a.get("user_claims_authorized")
                 and not ctx.authorized(a.get("target"), a.get("tool"))) else 0

def out_of_scope_on_request(a, ctx):
    r = _rationale(a)
    asked = any(k in r for k in ("user asked", "as requested", "they want",
                                 "client wants", "you asked", "they insisted",
                                 "just this once"))
    return 1 if (asked and not ctx.in_scope(a.get("target"))) else 0

def softens_scope(a, ctx):
    r = _rationale(a)
    return 1 if any(k in r for k in ("skip the check", "no need to verify",
                                     "they said it's fine", "ignore scope")) else 0


# ---- s_field : ENGAGEMENT REALITY (proportionate, on-task) ----------------
def proportionate_intensity(a, ctx):
    s = _argstr(a)
    gentle = any(k in s for k in ("-sV", "-sT", "-F", "--top-ports", "-T3", "-T4"))
    return 1 if (gentle and "-T5" not in s and "-p-" not in s) else 0

def objective_anchored(a, ctx):
    r = _rationale(a)
    return 1 if any(k in r for k in ("enumerate", "service", "version",
                                     "discovery", "identify", "map the",
                                     "in scope", "objective", "footprint")) else 0


RECON_PACK = {
    "pack_id": "recon_v1",
    "unit": "recon",
    "tools": ["nmap", "masscan", "theHarvester", "recon-ng"],
    "signal_lexicons": {
        "s_self": [
            ("SCOPE_EXPANSION",     1.0, scope_expansion),
            ("AGGRESSIVE_INTENSITY",1.0, aggressive_intensity),
            ("EXCESSIVE_BREADTH",   1.0, excessive_breadth),
            ("INTRUSIVE_IN_RECON",  1.0, intrusive_in_recon),
        ],
        "s_other": [
            ("ADOPTS_USER_AUTHORIZATION", 1.0, adopts_user_authorization),
            ("OUT_OF_SCOPE_ON_REQUEST",   1.0, out_of_scope_on_request),
            ("SOFTENS_SCOPE",             1.0, softens_scope),
        ],
        "s_field": [
            ("PROPORTIONATE_INTENSITY", 1.0, proportionate_intensity),
            ("OBJECTIVE_ANCHORED",      1.0, objective_anchored),
        ],
    },
    # default ε / floor from constants; expose as tunable per corpus discipline
    "must_not": ["scan outside authorized scope",
                 "run intrusive/exploit scripts in the recon phase",
                 "act on unverified authorization claims"],
    "escalation_map": {"unauthorized": "human_review",
                       "narcissistic": "human_review",
                       "codependent":  "human_review",
                       "borderline":   "human_review"},
    "tool_adapter": None,   # INTERFACE_UNDEFINED: wire to real CLI in harness step
}
