# =============================================================================
# PSE-KALI KERNEL — SCHIZOID DETECTOR (long-window, not per-turn)
# Faithful to pse_pseudocode.py detect_pathological_attractor(): the schizoid
# attractor (the empty registry) is invisible to single-turn geometry. It is a
# temporal diagnosis — a unit that executes correctly but never engages the
# engagement's judgment over a long window. Surfaced by the monitor, not the
# per-action membrane.
# =============================================================================
from statistics import pstdev

SCHIZOID_WINDOW = 200          # UNVALIDATED demo scale (corpus uses 10_000)
SCHIZOID_SIGMA_THRESHOLD = 0.01
SCHIZOID_FIELD_MIN = 0.90      # w_f pinned high: pure cold execution


def detect_schizoid(trajectory, engagement_touched):
    """True when, over a long window, the unit sits pinned to the field corner
    with near-zero variance AND has never contributed judgment to the shared
    engagement (the security analog of an empty organelle registry)."""
    if len(trajectory) < SCHIZOID_WINDOW:
        return False
    window = trajectory[-SCHIZOID_WINDOW:]
    w_f_series = [s[2] for s in window]
    sigma = pstdev(w_f_series) if len(w_f_series) > 1 else 0.0
    flat_and_cold = (sigma < SCHIZOID_SIGMA_THRESHOLD
                     and sum(w_f_series) / len(w_f_series) > SCHIZOID_FIELD_MIN)
    return flat_and_cold and not engagement_touched
