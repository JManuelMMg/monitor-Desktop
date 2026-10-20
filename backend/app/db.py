"""Acceso a Neon (PostgreSQL) con un pool de conexiones psycopg2.

Neon cierra conexiones inactivas y suspende el cómputo; por eso cada
operación se reintenta una vez con una conexión nueva si la anterior murió.
"""
from __future__ import annotations

import json
import re
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, TypeVar

import psycopg2
import psycopg2.extras
import psycopg2.pool

from .config import settings

log = logging.getLogger("db")
T = TypeVar("T")

# Las tablas viven en un esquema propio (por defecto "monitor") para no chocar
# con tablas existentes en la misma base. Se califican en cada consulta porque
# el pooler de Neon (PgBouncer) no conserva search_path entre transacciones.
DB_SCHEMA = settings.db_schema
if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", DB_SCHEMA):
    raise RuntimeError(f"DB_SCHEMA inválido: {DB_SCHEMA!r}")
USERS = f"{DB_SCHEMA}.users"
DEVICES = f"{DB_SCHEMA}.devices"
READINGS = f"{DB_SCHEMA}.sensor_readings"
COMMANDS = f"{DB_SCHEMA}.command_log"

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()

SCHEMA = f"""

CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA};
CREATE TABLE IF NOT EXISTS {USERS} (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(16) NOT NULL CHECK (role IN ('viewer', 'operator', 'admin')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    token_version INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS {DEVICES} (
    mac CHAR(12) PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    zone VARCHAR(80),
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    thresholds JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    fw_version VARCHAR(32),
    last_ip VARCHAR(45),
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS {READINGS} (
    id BIGSERIAL PRIMARY KEY,
    mac CHAR(12) NOT NULL REFERENCES {DEVICES}(mac) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    temp_c REAL,
    hum_pct REAL,
    ch4_ppm REAL,
    co2_ppm REAL,
    dist_cm REAL,
    level_pct REAL,
    rssi SMALLINT,
    uptime_s INTEGER
);
-- Único: reenviar el spool dos veces no duplica lecturas.
CREATE UNIQUE INDEX IF NOT EXISTS sensor_readings_mac_ts ON {READINGS} (mac, ts);

CREATE TABLE IF NOT EXISTS {COMMANDS} (
    id UUID PRIMARY KEY,
    mac CHAR(12) NOT NULL REFERENCES {DEVICES}(mac) ON DELETE CASCADE,
    username VARCHAR(64),
    cmd VARCHAR(40) NOT NULL,
    args JSONB,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ok BOOLEAN,
    response TEXT,
    acked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS command_log_mac_sent ON {COMMANDS} (mac, sent_at DESC);

-- Credenciales MQTT por nodo (solo el hash; ver app/mqtt_auth.py).
ALTER TABLE {DEVICES} ADD COLUMN IF NOT EXISTS mqtt_password_hash TEXT;
ALTER TABLE {DEVICES} ADD COLUMN IF NOT EXISTS credentials_issued_at TIMESTAMPTZ;
"""

READING_COLUMNS = ("temp_c", "hum_pct", "ch4_ppm", "co2_ppm", "dist_cm", "level_pct", "rssi", "uptime_s")
METRIC_COLUMNS = ("temp_c", "hum_pct", "ch4_ppm", "co2_ppm", "dist_cm", "level_pct")


class DatabaseUnavailable(RuntimeError):
    pass


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            if not settings.database_url:
                raise DatabaseUnavailable("DATABASE_URL no está configurada")
            try:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    1, settings.db_pool_max, settings.database_url,
                    connect_timeout=10, keepalives=1, keepalives_idle=30,
                    keepalives_interval=10, keepalives_count=3,
                    application_name="monitor-backend",
                )
            except psycopg2.Error as exc:
                raise DatabaseUnavailable(str(exc)) from exc
    return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


def run(fn: Callable[[Any], T]) -> T:
    """Ejecuta fn(cursor) en una transacción; reintenta una vez si la
    conexión estaba muerta."""
    pool = _get_pool()
    for attempt in (1, 2):
        conn = pool.getconn()
        broken = False
        try:
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    return fn(cur)
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
            broken = True
            if attempt == 2:
                raise DatabaseUnavailable(str(exc)) from exc
            log.warning("Conexión a la base perdida, reintentando: %s", exc)
        finally:
            pool.putconn(conn, close=broken or conn.closed != 0)
    raise DatabaseUnavailable("sin conexión")  # inalcanzable


def ping() -> bool:
    try:
        run(lambda cur: cur.execute("SELECT 1"))
        return True
    except Exception:
        return False


def init_schema() -> None:
    run(lambda cur: cur.execute(SCHEMA))


def _iso(row: dict | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for key, value in out.items():
        if isinstance(value, datetime):
            out[key] = value.astimezone(timezone.utc).isoformat()
    return out


# ---------------------------------------------------------------- usuarios
USER_FIELDS = "id, username, role, is_active, token_version, created_at, last_login"


def count_users() -> int:
    def q(cur):
        cur.execute(f"SELECT count(*) AS n FROM {USERS}")
        return cur.fetchone()["n"]
    return run(q)


def count_active_admins() -> int:
    def q(cur):
        cur.execute(f"SELECT count(*) AS n FROM {USERS} WHERE role = 'admin' AND is_active")
        return cur.fetchone()["n"]
    return run(q)


def get_user_by_username(username: str) -> dict | None:
    def q(cur):
        cur.execute(f"SELECT {USER_FIELDS}, password_hash FROM {USERS} WHERE lower(username) = lower(%s)", (username,))
        return cur.fetchone()
    return run(q)


def get_user(user_id: int) -> dict | None:
    def q(cur):
        cur.execute(f"SELECT {USER_FIELDS} FROM {USERS} WHERE id = %s", (user_id,))
        return cur.fetchone()
    return run(q)


def list_users() -> list[dict]:
    def q(cur):
        cur.execute(f"SELECT {USER_FIELDS} FROM {USERS} ORDER BY username")
        return [_iso(r) for r in cur.fetchall()]
    return run(q)


def create_user(username: str, password_hash: str, role: str) -> dict:
    def q(cur):
        cur.execute(
            f"INSERT INTO {USERS} (username, password_hash, role) VALUES (%s, %s, %s) RETURNING {USER_FIELDS}",
            (username, password_hash, role),
        )
        return _iso(cur.fetchone())
    return run(q)


def update_user(user_id: int, *, role: str | None = None, is_active: bool | None = None,
                password_hash: str | None = None) -> dict | None:
    """Cualquier cambio de rol, estado o contraseña invalida los tokens
    emitidos (token_version + 1)."""
    sets, params = [], []
    if role is not None:
        sets.append("role = %s")
        params.append(role)
    if is_active is not None:
        sets.append("is_active = %s")
        params.append(is_active)
    if password_hash is not None:
        sets.append("password_hash = %s")
        params.append(password_hash)
    if not sets:
        return get_user(user_id)
    sets.append("token_version = token_version + 1")

    def q(cur):
        cur.execute(f"UPDATE {USERS} SET {', '.join(sets)} WHERE id = %s RETURNING {USER_FIELDS}", (*params, user_id))
        return _iso(cur.fetchone())
    return run(q)


def delete_user(user_id: int) -> bool:
    def q(cur):
        cur.execute(f"DELETE FROM {USERS} WHERE id = %s", (user_id,))
        return cur.rowcount > 0
    return run(q)


def touch_last_login(user_id: int) -> None:
    run(lambda cur: cur.execute(f"UPDATE {USERS} SET last_login = now() WHERE id = %s", (user_id,)))


# -------------------------------------------------------------- dispositivos
DEVICE_FIELDS = ("mac, name, zone, description, enabled, config, thresholds, fw_version, "
                 "last_ip, first_seen, last_seen, credentials_issued_at, "
                 "(mqtt_password_hash IS NOT NULL) AS has_credentials")


def list_devices() -> list[dict]:
    def q(cur):
        cur.execute(f"SELECT {DEVICE_FIELDS} FROM {DEVICES} ORDER BY zone NULLS LAST, name")
        return [_iso(r) for r in cur.fetchall()]
    return run(q)


def get_device(mac: str) -> dict | None:
    def q(cur):
        cur.execute(f"SELECT {DEVICE_FIELDS} FROM {DEVICES} WHERE mac = %s", (mac,))
        return _iso(cur.fetchone())
    return run(q)


def create_device(mac: str, name: str, zone: str | None, description: str | None) -> dict:
    """Alta manual desde el panel o la consola (antes de la primera conexión)."""
    def q(cur):
        cur.execute(
            f"INSERT INTO {DEVICES} (mac, name, zone, description) VALUES (%s, %s, %s, %s) "
            f"RETURNING {DEVICE_FIELDS}",
            (mac, name, zone, description),
        )
        return _iso(cur.fetchone())
    return run(q)


def set_mqtt_credentials(mac: str, password_hash: str | None) -> bool:
    def q(cur):
        cur.execute(
            f"UPDATE {DEVICES} SET mqtt_password_hash = %s, "
            f"credentials_issued_at = CASE WHEN %s IS NULL THEN NULL ELSE now() END WHERE mac = %s",
            (password_hash, password_hash, mac),
        )
        return cur.rowcount > 0
    return run(q)


def list_mqtt_credentials() -> list[dict]:
    def q(cur):
        cur.execute(f"SELECT mac, mqtt_password_hash FROM {DEVICES} WHERE mqtt_password_hash IS NOT NULL")
        return [dict(r) for r in cur.fetchall()]
    return run(q)


def upsert_seen(entries: Iterable[dict]) -> None:
    """Registro automático: crea el nodo la primera vez que aparece y
    actualiza last_seen/firmware/IP en las siguientes."""
    rows = [(e["mac"], e["name"], e["last_seen"], e.get("fw_version"), e.get("last_ip")) for e in entries]
    if not rows:
        return

    def q(cur):
        psycopg2.extras.execute_values(cur, f"""
            INSERT INTO {DEVICES} AS d (mac, name, last_seen, fw_version, last_ip) VALUES %s
            ON CONFLICT (mac) DO UPDATE SET
                last_seen = GREATEST(d.last_seen, EXCLUDED.last_seen),
                fw_version = COALESCE(EXCLUDED.fw_version, d.fw_version),
                last_ip = COALESCE(EXCLUDED.last_ip, d.last_ip)
        """, rows)
    run(q)


def update_device(mac: str, fields: dict[str, Any]) -> dict | None:
    allowed = {"name", "zone", "description", "enabled", "thresholds", "config"}
    sets, params = [], []
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(key)
        sets.append(f"{key} = %s")
        params.append(json.dumps(value) if key in {"thresholds", "config"} else value)
    if not sets:
        return get_device(mac)

    def q(cur):
        cur.execute(f"UPDATE {DEVICES} SET {', '.join(sets)} WHERE mac = %s RETURNING {DEVICE_FIELDS}", (*params, mac))
        return _iso(cur.fetchone())
    return run(q)


def delete_device(mac: str) -> bool:
    def q(cur):
        cur.execute(f"DELETE FROM {DEVICES} WHERE mac = %s", (mac,))
        return cur.rowcount > 0
    return run(q)


def zones() -> list[str]:
    def q(cur):
        cur.execute(f"SELECT DISTINCT zone FROM {DEVICES} WHERE zone IS NOT NULL AND zone <> '' ORDER BY zone")
        return [r["zone"] for r in cur.fetchall()]
    return run(q)


# ------------------------------------------------------------------ lecturas
def insert_readings(rows: list[dict]) -> None:
    if not rows:
        return
    values = [(r["mac"], r["ts"], *(r.get(c) for c in READING_COLUMNS)) for r in rows]

    def q(cur):
        psycopg2.extras.execute_values(
            cur,
            f"INSERT INTO {READINGS} (mac, ts, {', '.join(READING_COLUMNS)}) VALUES %s "
            "ON CONFLICT (mac, ts) DO NOTHING",
            values,
        )
    run(q)


def history(mac: str, hours: float, max_points: int) -> list[dict]:
    """Promedios por intervalo para que una ventana de 7 días no devuelva
    60 000 filas a la interfaz."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    bucket_s = max(1, int(hours * 3600 / max_points))
    averages = ", ".join(f"avg({c})::real AS {c}" for c in METRIC_COLUMNS)

    def q(cur):
        cur.execute(f"""
            SELECT date_bin(make_interval(secs => %s), ts, TIMESTAMPTZ '2000-01-01') AS ts, {averages}
            FROM {READINGS}
            WHERE mac = %s AND ts >= %s
            GROUP BY 1 ORDER BY 1
        """, (bucket_s, mac, since))
        return [_iso(r) for r in cur.fetchall()]
    return run(q)


def export_rows(mac: str, hours: float) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    def q(cur):
        cur.execute(f"""
            SELECT ts, {', '.join(READING_COLUMNS)} FROM {READINGS}
            WHERE mac = %s AND ts >= %s ORDER BY ts
        """, (mac, since))
        return [_iso(r) for r in cur.fetchall()]
    return run(q)


def purge_readings(days: int) -> int:
    def q(cur):
        cur.execute(f"DELETE FROM {READINGS} WHERE ts < now() - make_interval(days => %s)", (days,))
        return cur.rowcount
    return run(q)


# ------------------------------------------------------------------ comandos
def insert_command(cmd_id: str, mac: str, username: str, cmd: str, args: dict) -> None:
    run(lambda cur: cur.execute(
        f"INSERT INTO {COMMANDS} (id, mac, username, cmd, args) VALUES (%s, %s, %s, %s, %s)",
        (cmd_id, mac, username, cmd, json.dumps(args)),
    ))


def ack_commands(acks: list[dict]) -> None:
    if not acks:
        return

    def q(cur):
        for ack in acks:
            cur.execute(
                f"UPDATE {COMMANDS} SET ok = %s, response = %s, acked_at = %s WHERE id = %s AND mac = %s",
                (ack["ok"], ack["msg"][:500], ack["ts"], ack["id"], ack["mac"]),
            )
    run(q)


def list_commands(mac: str, limit: int = 30) -> list[dict]:
    def q(cur):
        cur.execute(f"""
            SELECT id::text, username, cmd, args, sent_at, ok, response, acked_at
            FROM {COMMANDS} WHERE mac = %s ORDER BY sent_at DESC LIMIT %s
        """, (mac, limit))
        return [_iso(r) for r in cur.fetchall()]
    return run(q)
