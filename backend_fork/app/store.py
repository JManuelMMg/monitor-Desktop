"""Persistencia de telemetría con límite de frecuencia y búfer en disco si Neon no responde."""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from . import config, db

log = logging.getLogger("store")
_last_saved: Dict[str, float] = {}
_flush_lock = asyncio.Lock()


def to_row(device_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {"device_id": device_id, "ts": datetime.now(timezone.utc)}
    for metric in db.KNOWN_METRICS:
        value = payload.get(metric)
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        row[metric] = float(value) if ok else None
    row["ok"] = payload.get("ok") if isinstance(payload.get("ok"), dict) else None
    row["extra"] = {k: v for k, v in payload.items() if k not in db.KNOWN_METRICS and k != "ok"}
    return row


def _append_buffer(rows: List[Dict[str, Any]]) -> None:
    config.BUFFER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.BUFFER_FILE.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({**r, "ts": r["ts"].isoformat()}, default=str) + "\n")


def _read_buffer() -> List[Dict[str, Any]]:
    if not config.BUFFER_FILE.exists():
        return []
    rows = []
    for line in config.BUFFER_FILE.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            r["ts"] = datetime.fromisoformat(r["ts"])
            rows.append(r)
        except (ValueError, KeyError):
            continue
    return rows


async def save(device_id: str, payload: Dict[str, Any]) -> None:
    now = time.monotonic()
    if now - _last_saved.get(device_id, 0.0) < config.PERSIST_INTERVAL_S:
        return
    _last_saved[device_id] = now
    row = to_row(device_id, payload)
    try:
        await asyncio.to_thread(db.insert_telemetry, [row])
    except Exception as exc:
        log.warning("Neon no disponible, lectura al búfer local: %s", exc)
        await asyncio.to_thread(_append_buffer, [row])


async def flush_buffer() -> int:
    """Reintenta subir lo acumulado. Devuelve cuántas filas subió."""
    async with _flush_lock:
        rows = await asyncio.to_thread(_read_buffer)
        if not rows:
            return 0
        try:
            await asyncio.to_thread(db.insert_telemetry, rows)
        except Exception as exc:
            log.debug("Flush pospuesto: %s", exc)
            return 0
        config.BUFFER_FILE.unlink(missing_ok=True)
        log.info("Subidas %d lecturas del búfer a Neon", len(rows))
        return len(rows)
