from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.db import Database, get_db

SESSION_COOKIE = "matournee_session"
SESSION_DAYS = 30


class LoginPayload(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def auth_enabled(settings: Settings) -> bool:
    return bool(settings.auth_user and settings.auth_password)


def create_session(db: Database, username: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = (_utc_now() + timedelta(days=SESSION_DAYS)).replace(microsecond=0).isoformat()
    with db.write() as conn:
        conn.execute(
            "INSERT INTO sessions(token, username, expires_at) VALUES (?, ?, ?)",
            (token, username, expires),
        )
        conn.execute(
            "DELETE FROM sessions WHERE expires_at < ?",
            (_utc_now().replace(microsecond=0).isoformat(),),
        )
    return token


def delete_session(db: Database, token: Optional[str]) -> None:
    if not token:
        return
    with db.write() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_valid_session_user(db: Database, token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    with db.read() as conn:
        row = conn.execute(
            "SELECT username, expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    try:
        expires = datetime.fromisoformat(row["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    if expires < _utc_now():
        delete_session(db, token)
        return None
    return row["username"]


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_DAYS * 24 * 3600,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")


def verify_password(settings: Settings, username: str, password: str) -> bool:
    user_ok = secrets.compare_digest(
        username.encode("utf-8"),
        settings.auth_user.encode("utf-8"),
    )
    pass_ok = secrets.compare_digest(
        password.encode("utf-8"),
        settings.auth_password.encode("utf-8"),
    )
    return bool(user_ok and pass_ok)


def require_auth(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Database, Depends(get_db)],
) -> None:
    if not auth_enabled(settings):
        return
    token = request.cookies.get(SESSION_COOKIE)
    user = get_valid_session_user(db, token)
    if user:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise",
    )
