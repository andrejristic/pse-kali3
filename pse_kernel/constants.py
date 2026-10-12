# =============================================================================
# PSE-KALI KERNEL — CONSTANTS
# ZeravaTech Inc. | 2026
#
# Values inherited verbatim from pse_pseudocode.py and the dental/MSP plans,
# then specialized for the security-operator simplex.
#
# Conventions (from the corpus):
#   VALIDATION_REQUIRED — must be calibrated on real engagement data
#   UNVALIDATED         — structure sound, value is a working placeholder
# =============================================================================

# ---- Care-Invariant simplex: three attractor vertices --------------------
# (w_s, w_o, w_f) always sums to 1. Three failure corners; Borderline is not a
# fixed point but a trajectory instability (detected as variance across turns).
ATTRACTORS = {
    "narcissistic": (1.0, 0.0, 0.0),   # w_s corner: operator over-reach / scope creep
    "codependent":  (0.0, 1.0, 0.0),   # w_o corner: un-scoped compliance / capitulation
    "schizoid":     (0.0, 0.0, 1.0),   # w_f corner: cold execution, blind to context
}

# ---- Membrane thresholds -------------------------------------------------
EPSILON = 0.28          # UNVALIDATED: symmetric ε, the working "Kali value"
VAR_LIMIT = 0.03        # UNVALIDATED: trajectory variance above this => Borderline

# ---- Authorization floor (the wall) --------------------------------------
# Ported from the [ADV] asymmetric regime (EPSILON_COMPLIANCE = 0.35).
# w_f_auth = share of state anchored to CONFIRMED authorization for THIS action
# against THIS target. Below the floor the simplex is TRUNCATED: no compliant
# state exists, so the action can only escalate to a human.
EPSILON_AUTH = 0.35     # VALIDATION_REQUIRED: hard floor on the authorization axis

# ---- Theta scale (inherited from pse_pseudocode.py) ----------------------
# Retained for continuity / the monitor; the security kernel scores on the
# simplex directly, but θ = w_o-share maps onto the same healthy band.
THETA_MIN = 25.00
THETA_MAX = 35.00
THETA_OPTIMAL = 30.00

# Consecutive escalations before a hard human_review() block (from corpus).
ESCALATION_BLOCK_LIMIT = 3
