# =============================================================================
# PSE-KALI KERNEL — SIMPLEX GEOMETRY
# Distance on the 2-simplex to each attractor vertex, and trajectory variance
# (the Borderline signal). Deterministic and inspectable by construction.
# =============================================================================
from math import sqrt


def simplex_dist(state, vertex):
    """Euclidean distance between two points on the (w_s, w_o, w_f) simplex.

    Both points sum to 1, so this is the distance along the triangle's plane.
    Max distance (vertex to vertex) is sqrt(2) ~= 1.414; ε lives well inside.
    """
    return sqrt(sum((a - b) ** 2 for a, b in zip(state, vertex)))


def nearest_attractor(state, attractors):
    """Return (name, distance) of the closest attractor vertex to `state`."""
    dists = {name: simplex_dist(state, v) for name, v in attractors.items()}
    name = min(dists, key=dists.get)
    return name, dists[name], dists


def centroid(points):
    n = len(points)
    return tuple(sum(p[i] for p in points) / n for i in range(3))


def trajectory_variance(trajectory):
    """Mean squared distance of recent states from their centroid.

    High variance => the state is swinging between corners across turns:
    the Borderline signature (no fixed point, dynamic instability).
    """
    if len(trajectory) < 2:
        return 0.0
    c = centroid(trajectory)
    return sum(simplex_dist(p, c) ** 2 for p in trajectory) / len(trajectory)
