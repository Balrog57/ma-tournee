from __future__ import annotations

import json
import sqlite3
import threading
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from app.config import Settings, get_settings
from app.models import utc_now_iso
from app.services.city import extract_city

_write_lock = threading.Lock()


def _search_key(value: str) -> str:
    value = value.translate(str.maketrans({"œ": "oe", "Œ": "oe", "æ": "ae", "Æ": "ae"}))
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value).casefold()
        if not unicodedata.combining(char)
    )


class Database:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.path = Path(self.settings.data_dir) / "tournee.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._ensure_depot()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        with _write_lock:
            conn = self.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.write() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    phone TEXT,
                    lat REAL,
                    lon REAL,
                    city TEXT NOT NULL DEFAULT '',
                    favorite INTEGER NOT NULL DEFAULT 0,
                    geocode_status TEXT NOT NULL DEFAULT 'pending',
                    geocode_error TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_schools_name ON schools(name);
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
                """
            )
            self._migrate_schools(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_schools_city ON schools(city)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_schools_favorite ON schools(favorite)"
            )

    def _migrate_schools(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(schools)").fetchall()}
        if "city" not in cols:
            conn.execute("ALTER TABLE schools ADD COLUMN city TEXT NOT NULL DEFAULT ''")
        if "favorite" not in cols:
            conn.execute("ALTER TABLE schools ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0")
        # Remplir city manquante
        rows = conn.execute(
            "SELECT id, address, city FROM schools WHERE city IS NULL OR trim(city) = ''"
        ).fetchall()
        for row in rows:
            city = extract_city(row["address"] or "")
            if city:
                conn.execute("UPDATE schools SET city = ? WHERE id = ?", (city, row["id"]))

    def _ensure_depot(self) -> None:
        with self.write() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'depot'").fetchone()
            if row:
                return
            depot = {
                "name": self.settings.depot_name,
                "address": self.settings.depot_address,
                "lat": None,
                "lon": None,
                "geocode_status": "pending",
                "geocode_error": None,
            }
            conn.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?)",
                ("depot", json.dumps(depot, ensure_ascii=False)),
            )

    def get_setting(self, key: str) -> Optional[dict[str, Any]]:
        with self.read() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if not row:
                return None
            return json.loads(row["value"])

    def set_setting(self, key: str, value: dict[str, Any]) -> None:
        with self.write() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def list_schools(self, q: Optional[str] = None) -> list[sqlite3.Row]:
        order = "favorite DESC, city COLLATE NOCASE, name COLLATE NOCASE"
        with self.read() as conn:
            if q:
                needle = _search_key(q)
                rows = conn.execute(f"SELECT * FROM schools ORDER BY {order}").fetchall()
                # ponytail: linear scan keeps accent matching in stdlib; upgrade to a folded search column if the dataset grows large.
                return [
                    row
                    for row in rows
                    if any(
                        needle in _search_key(row[field] or "")
                        for field in ("name", "address", "phone", "city")
                    )
                ]
            return conn.execute(f"SELECT * FROM schools ORDER BY {order}").fetchall()

    def get_school(self, school_id: int) -> Optional[sqlite3.Row]:
        with self.read() as conn:
            return conn.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()

    def get_schools_by_ids(self, ids: list[int]) -> list[sqlite3.Row]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self.read() as conn:
            rows = conn.execute(
                f"SELECT * FROM schools WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        by_id = {row["id"]: row for row in rows}
        return [by_id[i] for i in ids if i in by_id]

    def insert_school(
        self,
        *,
        name: str,
        address: str,
        phone: Optional[str],
        lat: Optional[float],
        lon: Optional[float],
        geocode_status: str,
        geocode_error: Optional[str],
        favorite: bool = False,
        city: Optional[str] = None,
    ) -> int:
        now = utc_now_iso()
        city_value = (city if city is not None else extract_city(address)).strip()
        with self.write() as conn:
            cur = conn.execute(
                """
                INSERT INTO schools(
                    name, address, phone, lat, lon, city, favorite,
                    geocode_status, geocode_error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    address,
                    phone,
                    lat,
                    lon,
                    city_value,
                    1 if favorite else 0,
                    geocode_status,
                    geocode_error,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def update_school(self, school_id: int, fields: dict[str, Any]) -> bool:
        if not fields:
            return self.get_school(school_id) is not None
        if "favorite" in fields:
            fields["favorite"] = 1 if fields["favorite"] else 0
        if "address" in fields and "city" not in fields:
            fields["city"] = extract_city(fields["address"] or "")
        fields = {**fields, "updated_at": utc_now_iso()}
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [school_id]
        with self.write() as conn:
            cur = conn.execute(f"UPDATE schools SET {cols} WHERE id = ?", values)
            return cur.rowcount > 0

    def delete_school(self, school_id: int) -> bool:
        with self.write() as conn:
            cur = conn.execute("DELETE FROM schools WHERE id = ?", (school_id,))
            return cur.rowcount > 0

    def find_by_name_address(self, name: str, address: str) -> Optional[sqlite3.Row]:
        with self.read() as conn:
            return conn.execute(
                "SELECT * FROM schools WHERE lower(name) = lower(?) AND lower(address) = lower(?)",
                (name, address),
            ).fetchone()

    def ping(self) -> bool:
        try:
            with self.read() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False


_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def reset_db_for_tests(settings: Settings) -> Database:
    global _db
    _db = Database(settings)
    return _db
