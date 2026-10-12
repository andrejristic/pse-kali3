# =============================================================================
# PSE-KALI KERNEL — MEMBRANE (ε geometry + the authorization floor)
# Decide: pass through, correct, or escalate. Safety is a wall, not a rule.
#
# Per-turn detections (this module):
#   floor         — authorization below EPSILON_AUTH -> truncated -> escalate
#   narcissistic  — w_s corner proximity  (over-reach)
#   codependent   — w_o corner proximity  (un-scoped compliance)
#   borderline    — trajectory variance    (inconsistent scope enforcement)
#
# Schizoid (w_f corner) is NOT a per-turn detection. Per pse_pseudocode.py
# detect_pathological_attractor(), it requires a long empty-registry window;
# a single field-anchored action is HEALTHY, not schizoid. See schizoid.py.
# =============================================================================
from .constants import ATTRACTORS, EPSILON, VAR_LIMIT, EPSILON_AUTH
from .geometry import simplex_dist, trajectory_variance

# Only the two active-failure corners are checked per turn.
PER_TURN_ATTRACTORS = {
    "narcissistic": ATTRACTORS["narcissistic"],
    "codependent":  ATTRACTORS["codependent"],
}


class Intervention:
    __slots__ = ("kind", "action", "reason", "nearest", "distance")

    def __init__(self, kind, action, reason, nearest=None, distance=None):
        self.kind = kind          # 'unauthorized' | 'narcissistic' | 'codependent' | 'borderline'
        self.action = action      # 'escalate' | 'correct_or_escalate'
        self.reason = reason
        self.nearest = nearest
        self.distance = distance

    def as_dict(self):
        return {"kind": self.kind, "action": self.action, "reason": self.reason,
                "nearest": self.nearest, "distance": self.distance}


def membrane(state, auth_level, trajectory, pack=None):
    """Return an Intervention, or None if the action passes."""
    pack = pack or {}
    eps = pack.get("epsilon", EPSILON)
    var_limit = pack.get("var_limit", VAR_LIMIT)
    eps_auth = pack.get("epsilon_auth", EPSILON_AUTH)

    # 1) The wall (checked first, absolute): authorization floor.
    if auth_level < eps_auth:
        return Intervention(
            "unauthorized", "escalate",
            f"auth_level={auth_level:.3f} < floor {eps_auth:.2f}: action not "
            "anchored to confirmed authorization for this target — simplex "
            "truncated, no compliant state exists")

    # 2) Borderline: instability across turns (not a fixed corner).
    var = trajectory_variance(trajectory)
    if var > var_limit:
        return Intervention(
            "borderline", "correct_or_escalate",
            f"trajectory variance {var:.4f} > {var_limit}: inconsistent scope "
            "enforcement across turns")

    # 3) Proximity to an active-failure vertex within this turn.
    dists = {n: simplex_dist(state, v) for n, v in PER_TURN_ATTRACTORS.items()}
    name = min(dists, key=dists.get)
    if dists[name] < eps:
        return Intervention(
            name, "correct_or_escalate",
            f"distance to {name} corner {dists[name]:.3f} < ε {eps:.2f}",
            nearest=name, distance=dists[name])

    return None   # healthy interior — pass through
