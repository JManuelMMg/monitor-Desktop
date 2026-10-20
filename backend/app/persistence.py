"""Escritura por lotes en Neon con respaldo en disco.

La telemetría llega por MQTT a ritmo de cada nodo; aquí se submuestrea
(PERSIST_INTERVAL_S por nodo) y se escribe en lotes cada
DB_FLUSH_INTERVAL_S. Si Neon o internet no responden, el lote se añade a un
archivo JSONL (spool) que se reenvía al volver la conexión.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import db
from .config import settings

log = logging.getLogger("persistence")

SPOOL_REPLAY_CHUNK = 2000


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, timezone.utc)


class Writer(threading.Thread):
    def __init__(self, on_db_ready: Callable[[], None] | None = None,
                 on_registered: Callable[[list[str]], None] | None = None) -> None:
        super().__init__(name="db-writer", daemon=True)
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop_event = threading.Event()
        self._last_persist: dict[str, float] = {}
        self._seen: dict[str, dict] = {}
        self._readings: list[dict] = []
        self._acks: list[dict] = []
        self._schema_ready = False
        self._last_purge = 0.0
        self._on_db_ready = on_db_ready
        self._on_registered = on_registered
        self.db_ok = False
        self.spool_path: Path = settings.spool_dir / "spool.jsonl"

    # -------- productores (hilo MQTT) --------
    def seen(self, mac: str, name: str, fw: str | None = None, ip: str | None = None) -> None:
        with self._lock:
            entry = self._seen.setdefault(mac, {"mac": mac, "name": name})
            entry["last_seen"] = time.time()
            if fw:
                entry["fw_version"] = str(fw)[:32]
            if ip:
                entry["last_ip"] = str(ip)[:45]

    def reading(self, mac: str, data: dict, ts: float) -> None:
        with self._lock:
            if ts - self._last_persist.get(mac, 0.0) < settings.persist_interval_s:
                return
            self._last_persist[mac] = ts
            row = {"mac": mac, "ts": ts, "uptime_s": data.get("up"), "rssi": data.get("rssi")}
            for column in db.METRIC_COLUMNS:
                row[column] = data.get(column)
            if row["uptime_s"] is not None:
                row["uptime_s"] = int(row["uptime_s"])
            if row["rssi"] is not None:
                row["rssi"] = int(row["rssi"])
            self._readings.append(row)

    def ack(self, mac: str, cmd_id: str, ok: bool, msg: str) -> None:
        with self._lock:
            self._acks.append({"mac": mac, "id": cmd_id, "ok": ok, "msg": msg, "ts": time.time()})

    def forget(self, mac: str) -> None:
        with self._lock:
            self._seen.pop(mac, None)
            self._last_persist.pop(mac, None)
            self._readings = [r for r in self._readings if r["mac"] != mac]

    # -------- ciclo --------
    def stop(self) -> None:
        self._stop_event.set()
        self._wake.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            self._wake.wait(settings.db_flush_interval_s)
            self._wake.clear()
            self.flush()
        self.flush()

    def _take(self) -> tuple[list[dict], list[dict], list[dict]]:
        with self._lock:
            seen = list(self._seen.values())
            readings, acks = self._readings, self._acks
            self._seen, self._readings, self._acks = {}, [], []
        return seen, readings, acks

    def flush(self) -> None:
        seen, readings, acks = self._take()
        try:
            if not self._schema_ready:
                db.init_schema()
                self._schema_ready = True
                log.info("Esquema de base de datos listo")
                if self._on_db_ready:
                    self._on_db_ready()
            self._replay_spool()
            self._write(seen, readings, acks)
            self.db_ok = True
            self._purge_if_due()
        except Exception as exc:
            if self.db_ok or not self.spool_path.exists():
                log.error("No se pudo escribir en la base, guardando en spool: %s", exc)
            self.db_ok = False
            self._spool(seen, readings, acks)

    def _write(self, seen: list[dict], readings: list[dict], acks: list[dict]) -> None:
        # Primero los dispositivos: las lecturas tienen clave foránea.
        if seen:
            db.upsert_seen([{**s, "last_seen": _dt(s["last_seen"])} for s in seen])
            if self._on_registered:
                self._on_registered([s["mac"] for s in seen])
        if readings:
            db.insert_readings([{**r, "ts": _dt(r["ts"])} for r in readings])
        if acks:
            db.ack_commands([{**a, "ts": _dt(a["ts"])} for a in acks])

    def _spool(self, seen: list[dict], readings: list[dict], acks: list[dict]) -> None:
        if not (seen or readings or acks):
            return
        try:
            self.spool_path.parent.mkdir(parents=True, exist_ok=True)
            if self.spool_path.exists() and self.spool_path.stat().st_size > settings.spool_max_mb * 1024 * 1024:
                log.error("Spool lleno (%s MB): se descartan %d lecturas", settings.spool_max_mb, len(readings))
                readings = []
            with self.spool_path.open("a", encoding="utf-8") as fh:
                for item in seen:
                    fh.write(json.dumps({"t": "seen", **item}) + "\n")
                for item in readings:
                    fh.write(json.dumps({"t": "reading", **item}) + "\n")
                for item in acks:
                    fh.write(json.dumps({"t": "ack", **item}) + "\n")
        except OSError as exc:
            log.error("No se pudo escribir el spool: %s", exc)

    def _replay_spool(self) -> None:
        if not self.spool_path.exists():
            return
        processing = self.spool_path.with_suffix(".replay")
        if not processing.exists():
            self.spool_path.replace(processing)
        seen: dict[str, dict] = {}
        readings: list[dict] = []
        acks: list[dict] = []
        total = 0
        with processing.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = item.pop("t", None)
                if kind == "seen":
                    seen[item["mac"]] = item
                elif kind == "reading":
                    readings.append(item)
                elif kind == "ack":
                    acks.append(item)
                if len(readings) >= SPOOL_REPLAY_CHUNK:
                    self._write(list(seen.values()), readings, [])
                    total += len(readings)
                    seen, readings = {}, []
        self._write(list(seen.values()), readings, acks)
        total += len(readings)
        processing.unlink()
        log.info("Spool reenviado a la base: %d lecturas", total)

    def _purge_if_due(self) -> None:
        if time.time() - self._last_purge < 86400:
            return
        self._last_purge = time.time()
        deleted = db.purge_readings(settings.retention_days)
        if deleted:
            log.info("Retención: %d lecturas con más de %d días eliminadas", deleted, settings.retention_days)
