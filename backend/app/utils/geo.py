"""Geodesic helpers (haversine distance, great-circle interpolation)."""

from __future__ import annotations

from math import asin, cos, pi, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0

# GCJ-02 ("Mars coordinates") is the datum mandated for Chinese map services
# such as Amap. OSM/MapLibre basemaps use WGS-84, so Amap results must be
# shifted back before storage or pins land a few hundred metres off.
_GCJ_A = 6378245.0
_GCJ_EE = 0.00669342162296594323


def out_of_china(lat: float, lon: float) -> bool:
    """Rough bounding box: GCJ-02 only applies inside mainland China."""
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * sqrt(abs(x))
    ret += (20.0 * sin(6.0 * x * pi) + 20.0 * sin(2.0 * x * pi)) * 2.0 / 3.0
    ret += (20.0 * sin(y * pi) + 40.0 * sin(y / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * sin(y / 12.0 * pi) + 320 * sin(y * pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * sqrt(abs(x))
    ret += (20.0 * sin(6.0 * x * pi) + 20.0 * sin(2.0 * x * pi)) * 2.0 / 3.0
    ret += (20.0 * sin(x * pi) + 40.0 * sin(x / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * sin(x / 12.0 * pi) + 300.0 * sin(x / 30.0 * pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lat: float, lon: float) -> tuple[float, float]:
    """Convert WGS-84 ``(lat, lon)`` to GCJ-02 (no-op outside China)."""
    if out_of_china(lat, lon):
        return lat, lon
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    rad_lat = radians(lat)
    magic = sin(rad_lat)
    magic = 1 - _GCJ_EE * magic * magic
    sqrt_magic = sqrt(magic)
    dlat = (dlat * 180.0) / ((_GCJ_A * (1 - _GCJ_EE)) / (magic * sqrt_magic) * pi)
    dlon = (dlon * 180.0) / (_GCJ_A / sqrt_magic * cos(rad_lat) * pi)
    return lat + dlat, lon + dlon


def gcj02_to_wgs84(lat: float, lon: float) -> tuple[float, float]:
    """Convert GCJ-02 ``(lat, lon)`` back to WGS-84 via iteration."""
    if out_of_china(lat, lon):
        return lat, lon
    wgs_lat, wgs_lon = lat, lon
    for _ in range(3):
        gcj_lat, gcj_lon = wgs84_to_gcj02(wgs_lat, wgs_lon)
        wgs_lat += lat - gcj_lat
        wgs_lon += lon - gcj_lon
    return wgs_lat, wgs_lon


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
