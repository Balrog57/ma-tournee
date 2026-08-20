from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import (
    SESSION_COOKIE,
    LoginPayload,
    auth_enabled,
    clear_session_cookie,
    create_session,
    delete_session,
    get_valid_session_user,
    require_auth,
    set_session_cookie,
    verify_password,
)
from app.config import Settings, get_settings
from app.db import Database, get_db
from app.models import HealthOut, PublicConfig
from app.routers import schools, tours
from app.services.geocode import geocode_address, ping_geocoder
from app.services.routing import ping_router

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    db = get_db()
    depot = db.get_setting("depot")
    if depot and (depot.get("lat") is None or depot.get("lon") is None):
        result = await geocode_address(depot["address"], settings)
        if result.ok:
            depot["lat"] = result.lat
            depot["lon"] = result.lon
            depot["geocode_status"] = "ok"
            depot["geocode_error"] = None
            db.set_setting("depot", depot)
        elif not result.available:
            depot["geocode_status"] = "pending"
            depot["geocode_error"] = result.error
            db.set_setting("depot", depot)
        else:
            depot["geocode_status"] = "failed"
            depot["geocode_error"] = result.error
            db.set_setting("depot", depot)
    yield


app = FastAPI(title="Ma Tournée — L'Evasion", lifespan=lifespan, docs_url=None, redoc_url=None)
app.include_router(schools.router)
app.include_router(tours.router)


@app.get("/health", response_model=HealthOut)
async def health(settings: Settings = Depends(get_settings)) -> HealthOut:
    db_ok = get_db().ping()
    geocoder_ok = await ping_geocoder(settings)
    router_ok = await ping_router(settings)
    status = "ok" if db_ok else "degraded"
    if db_ok and not (geocoder_ok and router_ok):
        status = "degraded"
    return HealthOut(
        status=status,  # type: ignore[arg-type]
        database=db_ok,
        geocoder=geocoder_ok,
        router=router_ok,
        details={
            "geocoder_url": settings.geocoder_url,
            "router_url": settings.router_url,
        },
    )


@app.get("/api/config", response_model=PublicConfig, dependencies=[Depends(require_auth)])
def public_config(settings: Settings = Depends(get_settings)) -> PublicConfig:
    return PublicConfig(
        map_center_lat=settings.map_center_lat,
        map_center_lon=settings.map_center_lon,
        map_default_zoom=settings.map_default_zoom,
        tile_url=settings.tile_url,
        tile_attribution=settings.tile_attribution,
        depot_name=settings.depot_name,
        auth_enabled=auth_enabled(settings),
    )


@app.get("/api/auth/me")
def auth_me(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> dict:
    if not auth_enabled(settings):
        return {"authenticated": True, "auth_enabled": False, "username": None}
    user = get_valid_session_user(db, request.cookies.get(SESSION_COOKIE))
    return {
        "authenticated": bool(user),
        "auth_enabled": True,
        "username": user,
    }


@app.post("/api/auth/login")
def auth_login(
    payload: LoginPayload,
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> Response:
    if not auth_enabled(settings):
        return JSONResponse({"ok": True, "auth_enabled": False})
    if not verify_password(settings, payload.username.strip(), payload.password):
        raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect")
    token = create_session(db, settings.auth_user)
    response = JSONResponse({"ok": True, "username": settings.auth_user})
    set_session_cookie(response, token)
    return response


@app.post("/api/auth/logout")
def auth_logout(
    request: Request,
    db: Database = Depends(get_db),
) -> Response:
    delete_session(db, request.cookies.get(SESSION_COOKIE))
    response = JSONResponse({"ok": True})
    clear_session_cookie(response)
    return response


@app.get("/login")
def login_page(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> Response:
    if not auth_enabled(settings):
        return RedirectResponse("/", status_code=303)
    if get_valid_session_user(db, request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/", status_code=303)
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/")
def index(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> Response:
    if auth_enabled(settings) and not get_valid_session_user(db, request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/login", status_code=303)
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
