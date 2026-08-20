from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


GeocodeStatus = Literal["ok", "pending", "failed", "manual"]


class SchoolBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    address: str = Field(..., min_length=1, max_length=500)
    phone: Optional[str] = Field(None, max_length=40)

    @field_validator("name", "address", "phone", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = " ".join(value.strip().split())
            return cleaned or None
        return value


class SchoolCreate(SchoolBase):
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    favorite: bool = False


class SchoolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    phone: Optional[str] = Field(None, max_length=40)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    clear_coords: bool = False
    favorite: Optional[bool] = None

    @field_validator("name", "address", "phone", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = " ".join(value.strip().split())
            return cleaned or None
        return value


class SchoolOut(SchoolBase):
    id: int
    lat: Optional[float] = None
    lon: Optional[float] = None
    city: str = ""
    favorite: bool = False
    geocode_status: GeocodeStatus = "pending"
    geocode_error: Optional[str] = None
    updated_at: str


class DepotOut(BaseModel):
    name: str
    address: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    geocode_status: GeocodeStatus = "pending"
    geocode_error: Optional[str] = None


class DepotUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)

    @field_validator("name", "address", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = " ".join(value.strip().split())
            return cleaned or None
        return value


class TourRequest(BaseModel):
    school_ids: list[int] = Field(..., min_length=1, max_length=50)
    round_trip: bool = True


class TourStop(BaseModel):
    order: int
    kind: Literal["depot", "school"]
    id: Optional[int] = None
    name: str
    address: str
    lat: float
    lon: float


class TourResponse(BaseModel):
    mode: Literal["osrm", "haversine"]
    round_trip: bool
    stops: list[TourStop]
    distance_m: float
    duration_s: float
    geometry: dict
    warnings: list[str] = Field(default_factory=list)


class PublicConfig(BaseModel):
    map_center_lat: float
    map_center_lon: float
    map_default_zoom: int
    tile_url: str
    tile_attribution: str
    depot_name: str
    auth_enabled: bool


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    geocoder: bool
    router: bool
    details: dict = Field(default_factory=dict)


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
