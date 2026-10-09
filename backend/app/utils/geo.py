"""Geodesic helpers (haversine distance, great-circle interpolation)."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    rlat1, rlon1, rlat2, rlon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    h = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(min(1.0, sqrt(h)))


def great_circle_points(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    steps: int = 64,
) -> list[tuple[float, float]]:
    """Return ``steps + 1`` ``[lon, lat]`` tuples along the great circle.

    Uses spherical linear interpolation (slerp) so the drawn line follows
    the curvature of the Earth instead of a flat Mercator straight line.
    """
    import math

    φ1, λ1 = radians(lat1), radians(lon1)
    φ2, λ2 = radians(lat2), radians(lon2)
    Δ = 2 * asin(
        min(1.0, sqrt(sin((φ2 - φ1) / 2) ** 2 + cos(φ1) * cos(φ2) * sin((λ2 - λ1) / 2) ** 2)),
    )
    if Δ == 0:
        return [(lon1, lat1), (lon2, lat2)]
    points: list[tuple[float, float]] = []
    for i in range(steps + 1):
        f = i / steps
        a = sin((1 - f) * Δ) / sin(Δ)
        b = sin(f * Δ) / sin(Δ)
        x = a * cos(φ1) * cos(λ1) + b * cos(φ2) * cos(λ2)
        y = a * cos(φ1) * sin(λ1) + b * cos(φ2) * sin(λ2)
        z = a * sin(φ1) + b * sin(φ2)
        φ = math.atan2(z, math.sqrt(x * x + y * y))
        λ = math.atan2(y, x)
        points.append((math.degrees(λ), math.degrees(φ)))
    return points
