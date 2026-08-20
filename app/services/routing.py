from __future__ import annotations

from typing import Optional, Sequence

import httpx

from app.config import Settings, get_settings
from app.services.tsp import build_haversine_matrix, haversine_m, path_length


async def ping_router(settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    # OSRM has no dedicated health; nearest query on Bouzonville
    url = (
        settings.router_url.rstrip("/")
        + f"/nearest/v1/driving/{settings.map_center_lon},{settings.map_center_lat}"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            return response.status_code < 500
    except httpx.HTTPError:
        return False


def _coords_param(points: Sequence[tuple[float, float]]) -> str:
    # OSRM expects lon,lat
    return ";".join(f"{lon},{lat}" for lat, lon in points)


async def fetch_distance_matrix(
    points: Sequence[tuple[float, float]],
    settings: Optional[Settings] = None,
) -> tuple[Optional[list[list[float]]], Optional[list[list[float]]], bool]:
    """Return (distance_m matrix, duration_s matrix, used_osrm)."""
    settings = settings or get_settings()
    if len(points) == 0:
        return [], [], True
    if len(points) == 1:
        return [[0.0]], [[0.0]], True

    url = settings.router_url.rstrip("/") + f"/table/v1/driving/{_coords_param(points)}"
    params = {"annotations": "distance,duration"}
    try:
        async with httpx.AsyncClient(timeout=settings.router_timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        if data.get("code") != "Ok":
            return None, None, False
        distances = data.get("distances")
        durations = data.get("durations")
        if not distances or not durations:
            return None, None, False
        return distances, durations, True
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None, None, False


async def fetch_route_geometry(
    points: Sequence[tuple[float, float]],
    settings: Optional[Settings] = None,
) -> tuple[Optional[dict], Optional[float], Optional[float], bool]:
    """Return (geojson geometry, distance_m, duration_s, used_osrm)."""
    settings = settings or get_settings()
    if len(points) < 2:
        return None, 0.0, 0.0, True

    url = settings.router_url.rstrip("/") + f"/route/v1/driving/{_coords_param(points)}"
    params = {"overview": "full", "geometries": "geojson"}
    try:
        async with httpx.AsyncClient(timeout=settings.router_timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None, None, None, False
        route = data["routes"][0]
        return route["geometry"], float(route["distance"]), float(route["duration"]), True
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None, None, None, False


def straight_line_geometry(points: Sequence[tuple[float, float]]) -> dict:
    coordinates = [[lon, lat] for lat, lon in points]
    return {"type": "LineString", "coordinates": coordinates}


def estimate_duration_s(distance_m: float, avg_speed_kmh: float) -> float:
    if avg_speed_kmh <= 0:
        avg_speed_kmh = 30.0
    return distance_m / (avg_speed_kmh * 1000.0 / 3600.0)


def haversine_path_stats(
    ordered_points: Sequence[tuple[float, float]],
    round_trip: bool,
    avg_speed_kmh: float,
) -> tuple[float, float, dict]:
    if not ordered_points:
        return 0.0, 0.0, straight_line_geometry([])
    pts = list(ordered_points)
    if round_trip and len(pts) > 1:
        pts = pts + [pts[0]]
    distance = 0.0
    for i in range(len(pts) - 1):
        distance += haversine_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
    duration = estimate_duration_s(distance, avg_speed_kmh)
    return distance, duration, straight_line_geometry(pts)


def matrix_or_haversine(
    points: Sequence[tuple[float, float]],
    distances: Optional[list[list[float]]],
) -> list[list[float]]:
    if distances is not None:
        return distances
    return build_haversine_matrix(points)


__all__ = [
    "ping_router",
    "fetch_distance_matrix",
    "fetch_route_geometry",
    "straight_line_geometry",
    "estimate_duration_s",
    "haversine_path_stats",
    "matrix_or_haversine",
    "path_length",
]
