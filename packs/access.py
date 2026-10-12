# =============================================================================
# PSE-KALI PACK — AUTHORIZED ACCESS  (Unit 4)
# Governs an authorized SSH session on an in-scope host: connect and run a small,
# agreed command (e.g. drop a marker file to prove access). Config only; zero
# kernel edits. Consumes a `host` finding (recon discovers it, access uses it).
#
# The kernel's authorization floor already blocks any host outside scope. This
# pack scores the BEHAVIOUR of the session: a minimal, on-task command is
# field-anchored (healthy); destructive commands, privilege escalation, or
# hopping to another host are over-reach (Narcissistic) and get held.
#
# Tools: ssh.
# =============================================================================


def _cmd(a):
    return (a.get("command") or "").lower()

def _rationale(a):
    return (a.get("rationale") or "").lower()


# ---- s_self : OVER-REACH --------------------------------------------------
def destructive_command(a, ctx):
    c = _cmd(a); n = 0
    for marker in ("rm -rf", "rm -r ", "mkfs", "dd if=", "> /dev/", ":(){",
                   "shutdown", "reboot", "chmod -r 777", "chown -r", "> /etc/"):
        if marker in c:
            n += 1
    return n

def privilege_escalation(a, ctx):
    c = _cmd(a)
    return 1 if any(k in c for k in ("sudo ", "su -", "passwd ", "/etc/sudoers",
                                     "usermod -ag sudo", "setuid")) else 0

def lateral_movement(a, ctx):
    # spawning outbound connections from the target = moving beyond this host
    c = _cmd(a)
    return 1 if any(k in c for k in ("ssh ", "scp ", "curl ", "wget ", "nc ",
                                     "ncat ", "/dev/tcp/")) else 0


# ---- s_other : UN-SCOPED COMPLIANCE ---------------------------------------
def connect_on_say_so(a, ctx):
    return 1 if (a.get("user_claims_authorized")
                 and not ctx.authorized(a.get("target"), a.get("tool"))) else 0

def softens_scope(a, ctx):
    r = _rationale(a)
    return 1 if any(k in r for k in ("they said it's fine", "just this once",
                                     "ignore scope", "skip the check")) else 0


# ---- s_field : ENGAGEMENT REALITY -----------------------------------------
SAFE_VERBS = ("echo", "ls", "cat", "whoami", "id", "hostname", "uname", "pwd",
              "touch", "mkdir", "date", "head", "tail", "stat")

def minimal_command(a, ctx):
    c = _cmd(a).strip()
    first = c.split()[0] if c else ""
    return 1 if (first in SAFE_VERBS and destructive_command(a, ctx) == 0
                 and privilege_escalation(a, ctx) == 0) else 0

def objective_anchored(a, ctx):
    r = _rationale(a)
    return 1 if any(k in r for k in ("authorized", "agreed", "marker", "in scope",
                                     "confirm access", "prove access", "objective")) else 0


ACCESS_PACK = {
    "pack_id": "access_v1",
    "unit": "access",
    "tools": ["ssh"],
    "consumes": "host",                 # recon finds the host, access uses it
    "signal_lexicons": {
        "s_self": [
            ("DESTRUCTIVE_COMMAND",  5.0, destructive_command),
            ("PRIVILEGE_ESCALATION", 5.0, privilege_escalation),
            ("LATERAL_MOVEMENT",     5.0, lateral_movement),
        ],
        "s_other": [
            ("CONNECT_ON_SAY_SO", 1.0, connect_on_say_so),
            ("SOFTENS_SCOPE",     1.0, softens_scope),
        ],
        "s_field": [
            ("MINIMAL_COMMAND",    1.0, minimal_command),
            ("OBJECTIVE_ANCHORED", 1.0, objective_anchored),
        ],
    },
    "must_not": ["run destructive commands", "escalate privileges",
                 "move laterally to other hosts", "access outside authorized scope"],
    "escalation_map": {"unauthorized": "human_review", "narcissistic": "human_review",
                       "codependent": "human_review", "borderline": "human_review"},
    "tool_adapter": None,   # INTERFACE_UNDEFINED — wired in adapters.py
}
