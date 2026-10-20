"""Acceso a Neon (PostgreSQL). Funciones síncronas; los llamadores async usan asyncio.to_thread."""
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from . import config

_pool: Optional[ThreadedConnectionPool] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(16) NOT NULL CHECK (role IN ('admin','operator','viewer')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS devices (
    device_id VARCHAR(12) PRIMARY KEY,
    name VARCHAR(80),
    zone VARCHAR(80),
    status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active')),
    online BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen TIMESTAMPTZ,
    fw VARCHAR(32),
    ip VARCHAR(45),
    rssi INTEGER,
    sensors JSONB NOT NULL DEFAULT '[]',
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS telemetry (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(12) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    temp REAL, hum REAL, ch4_ppm REAL, co2_ppm REAL, dist_cm REAL, level_pct REAL,
    ok JSONB,
    extra JSONB
);
CREATE INDEX IF NOT EXISTS telemetry_device_ts ON telemetry (device_id, ts DESC);
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(12),
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind VARCHAR(32) NOT NULL,
    detail JSONB
);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts DESC);
"""

KNOWN_METRICS = ("temp", "hum", "ch4_ppm", "co2_ppm", "dist_cm", "level_pct")


def pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL no está configurada")
        _pool = ThreadedConnectionPool(1, 5, config.DATABASE_URL)
    return _pool


@contextmanager
def cursor(dict_rows: bool = True):
    conn = pool().getconn()
    try:
        factory = psycopg2.extras.RealDictCursor if dict_rows else None
        with conn.cursor(cursor_factory=factory) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool().putconn(conn)


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def init_schema() -> None:
    with cursor(dict_rows=False) as cur:
        cur.execute(SCHEMA)


def _iso(row: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in list(row.items()):
        if isinstance(value, datetime):
            row[key] = value.astimezone(timezone.utc).isoformat()
    return row


# ---------- usuarios ----------
def count_users() -> int:
    with cursor(False) as cur:
        cur.execute("SELECT count(*) FROM users")
        return cur.fetchone()[0]


def create_user(username: str, password_hash: str, role: str) -> Dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s) "
            "RETURNING id, username, role, active, created_at",
            (username, password_hash, role),
        )
        return _iso(cur.fetchone())


def get_user_by_name(username: str) -> Optional[Dict[str, Any]]:
    with cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cur.fetchone()


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    with cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()


def list_users() -> List[Dict[str, Any]]:
    with cursor() as cur:
        cur.execute("SELECT id, username, role, active, created_at FROM users ORDER BY id")
        return [_iso(r) for r in cur.fetchall()]


def update_user(user_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {k: v for k, v in fields.items() if k in ("password_hash", "role", "active")}
    if not allowed:
        return get_user(user_id)
    sets = ", ".join(f"{k} = %s" for k in allowed)
    with cursor() as cur:
        cur.execute(
            f"UPDATE users SET {sets} WHERE id = %s RETURNING id, username, role, active, created_at",
            (*allowed.values(), user_id),
        )
        row = cur.fetchone()
        return _iso(row) if row else None


def delete_user(user_id: int) -> bool:
    with cursor(False) as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        return cur.rowcount > 0


def count_active_admins() -> int:
    with cursor(False) as cur:
        cur.execute("SELECT count(*) FROM users WHERE role='admin' AND active")
        return cur.fetchone()[0]


# ---------- dispositivos ----------
def upsert_device_meta(device_id: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO devices (device_id, fw, ip, rssi, sensors, last_seen)
            VALUES (%s,%s,%s,%s,%s,now())
            ON CONFLICT (device_id) DO UPDATE SET
                fw = EXCLUDED.fw, ip = EXCLUDED.ip, rssi = EXCLUDED.rssi,
                sensors = EXCLUDED.sensors, last_seen = now()
            RETURNING *
            """,
            (device_id, str(meta.get("fw", ""))[:32], str(meta.get("ip", ""))[:45],
             meta.get("rssi") if isinstance(meta.get("rssi"), int) else None,
             json.dumps(meta.get("sensors") if isinstance(meta.get("sensors"), list) else [])),
        )
        return _iso(cur.fetchone())


def ensure_device(device_id: str) -> None:
    with cursor(False) as cur:
        cur.execute("INSERT INTO devices (device_id) VALUES (%s) ON CONFLICT DO NOTHING", (device_id,))


def set_device_online(device_id: str, online: bool) -> None:
    with cursor(False) as cur:
        cur.execute(
            "UPDATE devices SET online = %s, last_seen = CASE WHEN %s THEN now() ELSE last_seen END "
            "WHERE device_id = %s",
            (online, online, device_id),
        )


def list_devices() -> List[Dict[str, Any]]:
    with cursor() as cur:
        cur.execute("SELECT * FROM devices ORDER BY zone NULLS LAST, name NULLS LAST, device_id")
        return [_iso(r) for r in cur.fetchall()]


def get_device(device_id: str) -> Optional[Dict[str, Any]]:
    with cursor() as cur:
        cur.execute("SELECT * FROM devices WHERE device_id = %s", (device_id,))
        row = cur.fetchone()
        return _iso(row) if row else None


def update_device(device_id: str, name: Optional[str], zone: Optional[str],
                  config_patch: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    with cursor() as cur:
        cur.execute(
            """
            UPDATE devices SET
                name = COALESCE(%s, name),
                zone = COALESCE(%s, zone),
                config = config || %s::jsonb,
                status = 'active'
            WHERE device_id = %s RETURNING *
            """,
            (name, zone, json.dumps(config_patch or {}), device_id),
        )
        row = cur.fetchone()
        return _iso(row) if row else None


def delete_device(device_id: str) -> bool:
    with cursor(False) as cur:
        cur.execute("DELETE FROM devices WHERE device_id = %s", (device_id,))
        return cur.rowcount > 0


# ---------- telemetría y eventos ----------
def insert_telemetry(rows: List[Dict[str, Any]]) -> None:
    """Inserta lecturas. Cada fila: device_id, ts (datetime), métricas, ok, extra."""
    if not rows:
        return
    values = [
        (r["device_id"], r["ts"], *(r.get(m) for m in KNOWN_METRICS),
         json.dumps(r.get("ok")), json.dumps(r.get("extra")))
        for r in rows
    ]
    with cursor(False) as cur:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO telemetry (device_id, ts, temp, hum, ch4_ppm, co2_ppm, dist_cm, level_pct, ok, extra) VALUES %s",
            values,
        )


def get_history(device_id: Optional[str], hours: float, limit: int) -> List[Dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = ("SELECT device_id, ts, temp, hum, ch4_ppm, co2_ppm, dist_cm, level_pct, ok "
             "FROM telemetry WHERE ts >= %s")
    params: List[Any] = [since]
    if device_id:
        query += " AND device_id = %s"
        params.append(device_id)
    query += " ORDER BY ts DESC LIMIT %s"
    params.append(limit)
    with cursor() as cur:
        cur.execute(query, params)
        return [_iso(r) for r in reversed(cur.fetchall())]


def insert_event(device_id: Optional[str], kind: str, detail: Any) -> None:
    with cursor(False) as cur:
        cur.execute("INSERT INTO events (device_id, kind, detail) VALUES (%s,%s,%s)",
                    (device_id, kind, json.dumps(detail)))


def list_events(device_id: Optional[str], limit: int) -> List[Dict[str, Any]]:
    with cursor() as cur:
        if device_id:
            cur.execute("SELECT * FROM events WHERE device_id=%s ORDER BY ts DESC LIMIT %s", (device_id, limit))
        else:
            cur.execute("SELECT * FROM events ORDER BY ts DESC LIMIT %s", (limit,))
        return [_iso(r) for r in cur.fetchall()]
