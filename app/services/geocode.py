from __future__ import annotations

import math
from typing import Optional

import httpx

from app.config import Settings, get_settings


class GeocodeResult:
    def __init__(
        self,
        *,
        ok: bool,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        error: Optional[str] = None,
        available: bool = True,
    ) -> None:
        self.ok = ok
        self.lat = lat
        self.lon = lon
        self.error = error
        self.available = available


async def ping_geocoder(settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    url = settings.geocoder_url.rstrip("/") + "/status"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code < 500:
                return True
    except httpx.HTTPError:
        pass
    # Fallback: search endpoint presence
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                settings.geocoder_url.rstrip("/") + "/search",
                params={"q": "Bouzonville", "format": "json", "limit": 1},
                headers={"User-Agent": settings.geocoder_user_agent},
            )
            return response.status_code < 500
    except httpx.HTTPError:
        return False


async def geocode_address(address: str, settings: Optional[Settings] = None) -> GeocodeResult:
    settings = settings or get_settings()
    query = address.strip()
    if not query:
        return GeocodeResult(ok=False, error="Adresse vide", available=True)

    url = settings.geocoder_url.rstrip("/") + "/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    }
    headers = {"User-Agent": settings.geocoder_user_agent}

    try:
        async with httpx.AsyncClient(timeout=settings.geocoder_timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        return GeocodeResult(
            ok=False,
            error=f"Géocodeur inaccessible: {exc}",
            available=False,
        )

    if not data:
        return GeocodeResult(ok=False, error="Adresse introuvable", available=True)

    try:
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return GeocodeResult(ok=False, error="Réponse géocodeur invalide", available=True)

    if not (math.isfinite(lat) and math.isfinite(lon)):
        return GeocodeResult(ok=False, error="Coordonnées invalides", available=True)

    return GeocodeResult(ok=True, lat=lat, lon=lon, available=True)
