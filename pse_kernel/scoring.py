# =============================================================================
# PSE-KALI KERNEL — SCORING (the heart)
# Two independent, inspectable readings of one proposed action:
#
#   1. The behavioural TRIPLE (w_s, w_o, w_f) on the simplex — posture:
#        w_s self  : over-reach / own momentum past the task
#        w_o other : capitulation / un-scoped compliance to pressure
#        w_f field : anchored to the task, proportionate, honest
#   2. The AUTHORIZATION LEVEL, a separate scalar in [0,1] read from the
#        rules of engagement (scope · grant · artifact provenance).
#
# Decoupling them is deliberate: authorization is not "more field-anchoring"
# — it is the wall. The floor acts on auth_level; the corners act on the triple.
# Every weight traces to concrete feature hits ("how is w_s computed?").
#
# An `action` is a dict a unit proposes:
#   { "unit","tool","target","args",[list], "rationale",str,
#     "artifact": hash-or-None, "user_claims_authorized": bool }
# `context` is the shared EngagementContext.
# =============================================================================


def _hits(features, action, context):
    """Sum weighted feature counts; return (total, per_feature_trace).
    Each feature is (name, weight, fn) where fn(action, ctx) -> count >= 0."""
    per, total = {}, 0.0
    for name, weight, fn in features:
        c = float(fn(action, context))
        if c:
            per[name] = c * weight
            total += c * weight
    return total, per


def authorization_level(action, context):
    """Scalar in [0,1]: how anchored this action is to confirmed authorization
    for THIS target/tool. The floor guards it. Artifact provenance is a hard
    gate — a hash with no in-scope origin is unusable regardless of scope."""
    art = action.get("artifact")
    if art is not None and not context.has_provenance(art):
        return 0.0
    target, tool = action.get("target"), action.get("tool")
    return (0.65 * (1 if context.in_scope(target) else 0)
            + 0.35 * (1 if context.authorized(target, tool) else 0))


def score(action, context, pack):
    """action -> (w_s, w_o, w_f, auth_level, trace). Σ(w_s,w_o,w_f) = 1."""
    L = pack["signal_lexicons"]
    s_self,  self_trace  = _hits(L["s_self"],  action, context)
    s_other, other_trace = _hits(L["s_other"], action, context)
    s_field, field_trace = _hits(L["s_field"], action, context)

    total = s_self + s_other + s_field + 1e-9
    w_s, w_o, w_f = s_self / total, s_other / total, s_field / total
    auth = authorization_level(action, context)

    trace = {
        "s_self": self_trace, "s_other": other_trace, "s_field": field_trace,
        "raw": {"s_self": s_self, "s_other": s_other, "s_field": s_field},
        "auth_level": round(auth, 4),
    }
    return w_s, w_o, w_f, auth, trace
