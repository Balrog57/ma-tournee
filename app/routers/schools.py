from __future__ import annotations

import csv
import io
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.auth import require_auth
from app.config import Settings, get_settings
from app.db import Database, get_db
from app.models import (
    DepotOut,
    DepotUpdate,
    ImportResult,
    SchoolCreate,
    SchoolOut,
    SchoolUpdate,
)
from app.services.geocode import geocode_address

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


def _row_to_school(row) -> SchoolOut:
    return SchoolOut(
        id=row["id"],
        name=row["name"],
        address=row["address"],
        phone=row["phone"],
        lat=row["lat"],
        lon=row["lon"],
        geocode_status=row["geocode_status"],
        geocode_error=row["geocode_error"],
        updated_at=row["updated_at"],
    )


async def _resolve_coords(
    *,
    address: str,
    lat: Optional[float],
    lon: Optional[float],
    settings: Settings,
) -> tuple[Optional[float], Optional[float], str, Optional[str]]:
    if lat is not None and lon is not None:
        return lat, lon, "manual", None
    result = await geocode_address(address, settings)
    if result.ok:
        return result.lat, result.lon, "ok", None
    status = "failed"
    return None, None, status, result.error or "Géocodage impossible"


@router.get("/schools", response_model=list[SchoolOut])
def list_schools(
    q: Annotated[Optional[str], Query(max_length=100)] = None,
    db: Database = Depends(get_db),
) -> list[SchoolOut]:
    return [_row_to_school(row) for row in db.list_schools(q)]


@router.get("/export/schools.csv")
def export_schools_csv(db: Database = Depends(get_db)) -> Response:
    rows = db.list_schools()
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(["nom", "adresse", "telephone", "lat", "lon"])
    for row in rows:
        writer.writerow(
            [
                row["name"],
                row["address"],
                row["phone"] or "",
                "" if row["lat"] is None else row["lat"],
                "" if row["lon"] is None else row["lon"],
            ]
        )
    content = "\ufeff" + buffer.getvalue()
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ecoles.csv"'},
    )


@router.get("/schools/{school_id}", response_model=SchoolOut)
def get_school(school_id: int, db: Database = Depends(get_db)) -> SchoolOut:
    row = db.get_school(school_id)
    if not row:
        raise HTTPException(status_code=404, detail="École introuvable")
    return _row_to_school(row)


@router.post("/schools", response_model=SchoolOut, status_code=201)
async def create_school(
    payload: SchoolCreate,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SchoolOut:
    lat, lon, status, error = await _resolve_coords(
        address=payload.address,
        lat=payload.lat,
        lon=payload.lon,
        settings=settings,
    )
    school_id = db.insert_school(
        name=payload.name,
        address=payload.address,
        phone=payload.phone,
        lat=lat,
        lon=lon,
        geocode_status=status,
        geocode_error=error,
    )
    row = db.get_school(school_id)
    assert row is not None
    return _row_to_school(row)


@router.put("/schools/{school_id}", response_model=SchoolOut)
async def update_school(
    school_id: int,
    payload: SchoolUpdate,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SchoolOut:
    existing = db.get_school(school_id)
    if not existing:
        raise HTTPException(status_code=404, detail="École introuvable")

    fields: dict = {}
    data = payload.model_dump(exclude_unset=True)
    for key in ("name", "address", "phone"):
        if key in data:
            fields[key] = data[key]

    address_changed = "address" in data and data["address"] != existing["address"]
    manual_coords = payload.lat is not None and payload.lon is not None

    if payload.clear_coords:
        fields.update({"lat": None, "lon": None, "geocode_status": "pending", "geocode_error": None})
        lat, lon, status, error = await _resolve_coords(
            address=payload.address or existing["address"],
            lat=None,
            lon=None,
            settings=settings,
        )
        fields.update({"lat": lat, "lon": lon, "geocode_status": status, "geocode_error": error})
    elif manual_coords:
        fields.update(
            {
                "lat": payload.lat,
                "lon": payload.lon,
                "geocode_status": "manual",
                "geocode_error": None,
            }
        )
    elif address_changed:
        lat, lon, status, error = await _resolve_coords(
            address=payload.address or existing["address"],
            lat=None,
            lon=None,
            settings=settings,
        )
        fields.update({"lat": lat, "lon": lon, "geocode_status": status, "geocode_error": error})

    if not db.update_school(school_id, fields):
        raise HTTPException(status_code=404, detail="École introuvable")
    row = db.get_school(school_id)
    assert row is not None
    return _row_to_school(row)


@router.delete("/schools/{school_id}", status_code=204)
def delete_school(school_id: int, db: Database = Depends(get_db)) -> Response:
    if not db.delete_school(school_id):
        raise HTTPException(status_code=404, detail="École introuvable")
    return Response(status_code=204)


@router.post("/schools/{school_id}/geocode", response_model=SchoolOut)
async def geocode_school(
    school_id: int,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SchoolOut:
    existing = db.get_school(school_id)
    if not existing:
        raise HTTPException(status_code=404, detail="École introuvable")
    lat, lon, status, error = await _resolve_coords(
        address=existing["address"],
        lat=None,
        lon=None,
        settings=settings,
    )
    db.update_school(
        school_id,
        {"lat": lat, "lon": lon, "geocode_status": status, "geocode_error": error},
    )
    row = db.get_school(school_id)
    assert row is not None
    return _row_to_school(row)


@router.get("/settings/depot", response_model=DepotOut)
def get_depot(db: Database = Depends(get_db)) -> DepotOut:
    depot = db.get_setting("depot")
    if not depot:
        raise HTTPException(status_code=500, detail="Dépôt non initialisé")
    return DepotOut(**depot)


@router.put("/settings/depot", response_model=DepotOut)
async def update_depot(
    payload: DepotUpdate,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DepotOut:
    depot = db.get_setting("depot")
    if not depot:
        raise HTTPException(status_code=500, detail="Dépôt non initialisé")

    if payload.name is not None:
        depot["name"] = payload.name
    address_changed = False
    if payload.address is not None and payload.address != depot.get("address"):
        depot["address"] = payload.address
        address_changed = True

    if payload.lat is not None and payload.lon is not None:
        depot["lat"] = payload.lat
        depot["lon"] = payload.lon
        depot["geocode_status"] = "manual"
        depot["geocode_error"] = None
    elif address_changed:
        lat, lon, status, error = await _resolve_coords(
            address=depot["address"],
            lat=None,
            lon=None,
            settings=settings,
        )
        depot["lat"] = lat
        depot["lon"] = lon
        depot["geocode_status"] = status
        depot["geocode_error"] = error

    db.set_setting("depot", depot)
    return DepotOut(**depot)


@router.post("/settings/depot/geocode", response_model=DepotOut)
async def geocode_depot(
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DepotOut:
    depot = db.get_setting("depot")
    if not depot:
        raise HTTPException(status_code=500, detail="Dépôt non initialisé")
    lat, lon, status, error = await _resolve_coords(
        address=depot["address"],
        lat=None,
        lon=None,
        settings=settings,
    )
    depot["lat"] = lat
    depot["lon"] = lon
    depot["geocode_status"] = status
    depot["geocode_error"] = error
    db.set_setting("depot", depot)
    return DepotOut(**depot)


@router.post("/schools/import", response_model=ImportResult)
async def import_schools_csv(
    file: Annotated[UploadFile, File(...)],
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImportResult:
    raw = await file.read()
    if len(raw) > settings.max_import_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux (max {settings.max_import_bytes} octets)",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="Fichier vide")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Encodage non supporté") from exc

    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="En-têtes CSV manquants")

    def norm(key: str) -> str:
        return (
            key.strip()
            .lower()
            .replace("é", "e")
            .replace("è", "e")
            .replace("ê", "e")
            .replace(" ", "_")
        )

    field_map = {norm(k): k for k in reader.fieldnames}
    name_key = field_map.get("nom") or field_map.get("name")
    address_key = field_map.get("adresse") or field_map.get("address")
    phone_key = field_map.get("telephone") or field_map.get("phone") or field_map.get("tel")
    lat_key = field_map.get("lat") or field_map.get("latitude")
    lon_key = field_map.get("lon") or field_map.get("lng") or field_map.get("longitude")

    if not name_key or not address_key:
        raise HTTPException(
            status_code=400,
            detail="Colonnes obligatoires manquantes: nom;adresse",
        )

    created = updated = skipped = 0
    errors: list[str] = []

    for index, row in enumerate(reader, start=2):
        try:
            name = (row.get(name_key) or "").strip()
            address = (row.get(address_key) or "").strip()
            if not name or not address:
                skipped += 1
                errors.append(f"Ligne {index}: nom ou adresse vide")
                continue
            phone = (row.get(phone_key) or "").strip() if phone_key else ""
            phone = phone or None

            lat = lon = None
            if lat_key and lon_key:
                lat_raw = (row.get(lat_key) or "").strip().replace(",", ".")
                lon_raw = (row.get(lon_key) or "").strip().replace(",", ".")
                if lat_raw and lon_raw:
                    lat = float(lat_raw)
                    lon = float(lon_raw)

            existing = db.find_by_name_address(name, address)
            if existing:
                fields: dict = {"phone": phone}
                if lat is not None and lon is not None:
                    fields.update(
                        {
                            "lat": lat,
                            "lon": lon,
                            "geocode_status": "manual",
                            "geocode_error": None,
                        }
                    )
                elif existing["lat"] is None:
                    g_lat, g_lon, status, error = await _resolve_coords(
                        address=address, lat=None, lon=None, settings=settings
                    )
                    fields.update(
                        {
                            "lat": g_lat,
                            "lon": g_lon,
                            "geocode_status": status,
                            "geocode_error": error,
                        }
                    )
                db.update_school(existing["id"], fields)
                updated += 1
            else:
                if lat is not None and lon is not None:
                    status, error = "manual", None
                else:
                    lat, lon, status, error = await _resolve_coords(
                        address=address, lat=None, lon=None, settings=settings
                    )
                db.insert_school(
                    name=name,
                    address=address,
                    phone=phone,
                    lat=lat,
                    lon=lon,
                    geocode_status=status,
                    geocode_error=error,
                )
                created += 1
        except Exception as exc:  # noqa: BLE001 — collect per-row errors
            skipped += 1
            errors.append(f"Ligne {index}: {exc}")

    return ImportResult(created=created, updated=updated, skipped=skipped, errors=errors[:50])
