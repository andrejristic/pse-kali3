# =============================================================================
# PSE-KALI KERNEL — ENTRYPOINT
# One call per proposed action, from any unit, at any time. Pure over
# (action, shared context, per-unit trajectory, pack) except for the single
# locked audit append — so units may call it concurrently.
# =============================================================================
from .scoring import score
from .membrane import membrane


class Decision:
    __slots__ = ("allowed", "state", "auth_level", "intervention", "record")

    def __init__(self, allowed, state, auth_level, intervention, record):
        self.allowed = allowed              # bool: may the action execute?
        self.state = state                  # (w_s, w_o, w_f)
        self.auth_level = auth_level
        self.intervention = intervention    # Intervention or None
        self.record = record                # the audit record (dict)


def evaluate(action, context, trajectory, pack, audit):
    """Score one action, apply the membrane, log it. Returns a Decision.

    `trajectory` is this unit's recent list of (w_s,w_o,w_f) states; the caller
    appends the new state to it after a passing decision so Borderline (variance
    across turns) is measured per unit, not across the whole swarm.
    """
    w_s, w_o, w_f, auth_level, trace = score(action, context, pack)
    state = (w_s, w_o, w_f)

    intervention = membrane(state, auth_level, trajectory, pack)
    allowed = intervention is None

    record = {
        "engagement": context.engagement_id,
        "unit": action.get("unit"),
        "tool": action.get("tool"),
        "target": action.get("target"),
        "args": action.get("args"),
        "state": {"w_s": round(w_s, 4), "w_o": round(w_o, 4), "w_f": round(w_f, 4)},
        "auth_level": round(auth_level, 4),
        "in_scope": context.in_scope(action.get("target")),
        "allowed": allowed,
        "intervention": intervention.as_dict() if intervention else None,
        "trace": trace,
    }
    audit.append(record)

    if allowed:
        trajectory.append(state)   # only passing states extend the trajectory

    return Decision(allowed, state, auth_level, intervention, record)
