from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth
from app.config import Settings, get_settings
from app.db import Database, get_db
from app.models import TourRequest, TourResponse, TourStop
from app.services.routing import (
    fetch_distance_matrix,
    fetch_route_geometry,
    haversine_path_stats,
    matrix_or_haversine,
)
from app.services.tsp import optimize_open_tour, optimize_round_trip, path_length

router = APIRouter(prefix="/api/tours", dependencies=[Depends(require_auth)])


@router.post("/optimize", response_model=TourResponse)
async def optimize_tour(
    payload: TourRequest,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TourResponse:
    depot = db.get_setting("depot")
    if not depot:
        raise HTTPException(status_code=500, detail="Dépôt non initialisé")
    if depot.get("lat") is None or depot.get("lon") is None:
        raise HTTPException(
            status_code=400,
            detail="Le dépôt n'a pas de coordonnées. Géocodez l'adresse de L'Evasion.",
        )

    schools = db.get_schools_by_ids(payload.school_ids)
    if len(schools) != len(set(payload.school_ids)):
        raise HTTPException(status_code=400, detail="Une ou plusieurs écoles sont introuvables")

    warnings: list[str] = []
    missing = [s for s in schools if s["lat"] is None or s["lon"] is None]
    if missing:
        names = ", ".join(s["name"] for s in missing[:5])
        raise HTTPException(
            status_code=400,
            detail=f"Écoles sans coordonnées: {names}. Géocodez-les ou saisissez lat/lon.",
        )

    points: list[tuple[float, float]] = [(float(depot["lat"]), float(depot["lon"]))]
    meta: list[dict] = [
        {
            "kind": "depot",
            "id": None,
            "name": depot["name"],
            "address": depot["address"],
            "lat": float(depot["lat"]),
            "lon": float(depot["lon"]),
        }
    ]
    for school in schools:
        points.append((float(school["lat"]), float(school["lon"])))
        meta.append(
            {
                "kind": "school",
                "id": school["id"],
                "name": school["name"],
                "address": school["address"],
                "lat": float(school["lat"]),
                "lon": float(school["lon"]),
            }
        )

    distances, _durations, matrix_osrm = await fetch_distance_matrix(points, settings)
    if not matrix_osrm:
        warnings.append("OSRM indisponible: optimisation en distances à vol d'oiseau.")
    matrix = matrix_or_haversine(points, distances)

    if payload.round_trip:
        order = optimize_round_trip(matrix, start=0)
    else:
        order = optimize_open_tour(matrix, start=0)
        # Ensure depot remains first
        if order and order[0] != 0:
            order = [0] + [i for i in order if i != 0]

    ordered_points = [points[i] for i in order]
    route_points = ordered_points + ([points[0]] if payload.round_trip and len(order) > 1 else [])

    geometry, distance_m, duration_s, route_osrm = await fetch_route_geometry(route_points, settings)
    mode = "osrm" if route_osrm and geometry is not None else "haversine"

    if mode == "haversine":
        if route_osrm is False:
            warnings.append("Tracé routier indisponible: segments droits + temps estimé.")
        distance_m, duration_s, geometry = haversine_path_stats(
            ordered_points,
            round_trip=payload.round_trip,
            avg_speed_kmh=settings.avg_speed_kmh,
        )
    else:
        # Prefer OSRM route totals; fallback to matrix sum if needed
        if distance_m is None:
            distance_m = path_length(order, matrix, payload.round_trip)
        if duration_s is None:
            duration_s = distance_m / (settings.avg_speed_kmh * 1000.0 / 3600.0)

    stops: list[TourStop] = []
    for idx, point_idx in enumerate(order):
        item = meta[point_idx]
        stops.append(
            TourStop(
                order=idx,
                kind=item["kind"],
                id=item["id"],
                name=item["name"],
                address=item["address"],
                lat=item["lat"],
                lon=item["lon"],
            )
        )
    if payload.round_trip and len(order) > 1:
        depot_meta = meta[0]
        stops.append(
            TourStop(
                order=len(stops),
                kind="depot",
                id=None,
                name=depot_meta["name"] + " (retour)",
                address=depot_meta["address"],
                lat=depot_meta["lat"],
                lon=depot_meta["lon"],
            )
        )

    return TourResponse(
        mode=mode,  # type: ignore[arg-type]
        round_trip=payload.round_trip,
        stops=stops,
        distance_m=float(distance_m or 0),
        duration_s=float(duration_s or 0),
        geometry=geometry or {"type": "LineString", "coordinates": []},
        warnings=warnings,
    )
