"""Estado en vivo de los nodos (memoria) y normalización de telemetría."""
from __future__ import annotations

import copy
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import settings
from .topics import format_mac

DEFAULT_CONFIG: dict[str, Any] = {
    "rev": 0,
    "interval_ms": 5000,
    "dht_temp_offset": 0.0,
    "dht_hum_offset": 0.0,
    "us_offset_cm": 0.0,
    "us_scale": 1.0,
    "reactor_empty_cm": 100.0,
    "reactor_full_cm": 10.0,
    "co2_abc": False,
    "status_led": True,
}

DEFAULT_THRESHOLDS: dict[str, float] = {
    "temp_c_max": 38.0,
    "ch4_ppm_max": 5000.0,     # 10 % del LEL del metano
    "co2_ppm_max": 5000.0,
    "level_pct_max": 90.0,
}

# campo -> (mínimo, máximo) físicamente plausibles
TELEMETRY_RANGES: dict[str, tuple[float, float]] = {
    "temp_c": (-40, 85),
    "hum_pct": (0, 100),
    "ch4_ppm": (0, 50000),
    "co2_ppm": (0, 10000),
    "dist_cm": (0, 500),
    "level_pct": (0, 100),
    "mq_rs_kohm": (0, 2000),
    "rssi": (-127, 0),
    "up": (0, 2 ** 32),
    "heap": (0, 2 ** 32),
    "seq": (0, 2 ** 32),
    "mqtt_reconnects": (0, 2 ** 32),
}
TELEMETRY_FLAGS = ("dht_ok", "co2_ok", "mq_warm", "mq_cal", "mq_ok", "mq_calibrating", "us_ok")


def normalize_telemetry(payload: dict) -> dict:
    """Solo pasan campos conocidos; valores no numéricos, infinitos o fuera
    de rango se convierten en None."""
    out: dict[str, Any] = {}
    for key, (low, high) in TELEMETRY_RANGES.items():
        value = payload.get(key)
        if value is None or isinstance(value, bool):
            out[key] = None
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            out[key] = None
            continue
        out[key] = number if math.isfinite(number) and low <= number <= high else None
    for flag in TELEMETRY_FLAGS:
        out[flag] = payload.get(flag) is True
    return out


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None


def default_name(mac: str) -> str:
    return f"Nodo {mac[-4:].upper()}"


@dataclass
class NodeState:
    mac: str
    name: str
    zone: str | None = None
    description: str | None = None
    enabled: bool = True
    in_db: bool = False
    config: dict = field(default_factory=lambda: copy.deepcopy(DEFAULT_CONFIG))
    thresholds: dict = field(default_factory=dict)
    config_state: dict | None = None
    online: bool = False
    status: dict = field(default_factory=dict)
    last_seen: float | None = None
    telemetry: dict | None = None
    telemetry_ts: float | None = None
    last_connection: str = "offline"
    has_credentials: bool = False
    credentials_issued_at: str | None = None

    def effective_thresholds(self) -> dict:
        merged = dict(DEFAULT_THRESHOLDS)
        merged.update({k: v for k, v in self.thresholds.items() if k in DEFAULT_THRESHOLDS})
        return merged

    def connection(self, now: float) -> str:
        if not self.online:
            return "offline"
        interval_s = (self.config_state or self.config).get("interval_ms", 5000) / 1000
        stale_after = max(settings.stale_after_s, 3 * interval_s)
        if self.telemetry_ts is None or now - self.telemetry_ts > stale_after:
            return "stale"
        return "online"

    def alarms(self) -> list[dict]:
        if not self.enabled or not self.telemetry:
            return []
        limits = self.effective_thresholds()
        found = []
        for metric in ("temp_c", "ch4_ppm", "co2_ppm", "level_pct"):
            value = self.telemetry.get(metric)
            limit = limits.get(f"{metric}_max")
            if value is not None and limit is not None and value > limit:
                found.append({"metric": metric, "value": value, "limit": limit})
        return found

    def snapshot(self, now: float | None = None) -> dict:
        now = now or time.time()
        reported_rev = (self.config_state or {}).get("rev")
        return {
            "mac": self.mac,
            "mac_display": format_mac(self.mac),
            "name": self.name,
            "zone": self.zone,
            "description": self.description,
            "enabled": self.enabled,
            "registered": self.in_db,
            "has_credentials": self.has_credentials,
            "credentials_issued_at": self.credentials_issued_at,
            "first_connection_pending": self.in_db and self.last_seen is None,
            "connection": self.connection(now),
            "fw_version": self.status.get("fw"),
            "ip": self.status.get("ip"),
            "reset_reason": self.status.get("reset_reason"),
            "last_seen": _iso(self.last_seen),
            "telemetry": self.telemetry,
            "telemetry_ts": _iso(self.telemetry_ts),
            "alarms": self.alarms(),
            "thresholds": self.effective_thresholds(),
            "config": self.config,
            "config_state": self.config_state,
            "config_pending": self.config.get("rev", 0) != reported_rev,
        }


class Registry:
    def __init__(self) -> None:
        self._nodes: dict[str, NodeState] = {}
        self._lock = threading.Lock()

    def _ensure(self, mac: str) -> tuple[NodeState, bool]:
        node = self._nodes.get(mac)
        if node is None:
            node = NodeState(mac=mac, name=default_name(mac))
            self._nodes[mac] = node
            return node, True
        return node, False

    def load(self, rows: list[dict]) -> None:
        with self._lock:
            for row in rows:
                node, _ = self._ensure(row["mac"])
                self._apply_row(node, row)

    @staticmethod
    def _apply_row(node: NodeState, row: dict) -> None:
        node.in_db = True
        node.name = row["name"]
        node.zone = row.get("zone")
        node.description = row.get("description")
        node.enabled = row.get("enabled", True)
        node.thresholds = row.get("thresholds") or {}
        node.has_credentials = bool(row.get("has_credentials"))
        node.credentials_issued_at = row.get("credentials_issued_at")
        # Tras reiniciar el backend, lo último conocido sale de la base hasta
        # que el nodo vuelva a hablar.
        if node.last_seen is None and row.get("last_seen"):
            node.last_seen = datetime.fromisoformat(row["last_seen"]).timestamp()
        if not node.status.get("fw") and row.get("fw_version"):
            node.status = {**node.status, "fw": row["fw_version"], "ip": row.get("last_ip")}
        config = copy.deepcopy(DEFAULT_CONFIG)
        config.update(row.get("config") or {})
        node.config = config

    def apply_row(self, row: dict) -> dict:
        with self._lock:
            node, _ = self._ensure(row["mac"])
            self._apply_row(node, row)
            return node.snapshot()

    def mark_registered(self, macs: list[str]) -> None:
        with self._lock:
            for mac in macs:
                if mac in self._nodes:
                    self._nodes[mac].in_db = True

    def on_status(self, mac: str, payload: dict) -> tuple[dict, NodeState, bool]:
        now = time.time()
        with self._lock:
            node, created = self._ensure(mac)
            node.online = payload.get("state") == "online"
            if node.online:
                node.status = {k: payload.get(k) for k in ("fw", "ip", "rssi", "reset_reason", "interval_ms")}
                node.last_seen = now
            node.last_connection = node.connection(now)
            return node.snapshot(now), node, created

    def on_telemetry(self, mac: str, data: dict) -> tuple[dict, NodeState, bool]:
        now = time.time()
        with self._lock:
            node, created = self._ensure(mac)
            # Recibir telemetría implica que el nodo está conectado aunque el
            # status retenido se haya perdido.
            node.online = True
            node.telemetry = data
            node.telemetry_ts = now
            node.last_seen = now
            node.last_connection = node.connection(now)
            return node.snapshot(now), node, created

    def on_config_state(self, mac: str, payload: dict) -> dict:
        with self._lock:
            node, _ = self._ensure(mac)
            node.config_state = payload
            return node.snapshot()

    def set_config(self, mac: str, config: dict) -> dict | None:
        with self._lock:
            node = self._nodes.get(mac)
            if node is None:
                return None
            node.config = config
            return node.snapshot()

    def get(self, mac: str) -> NodeState | None:
        with self._lock:
            return self._nodes.get(mac)

    def snapshot(self, mac: str) -> dict | None:
        with self._lock:
            node = self._nodes.get(mac)
            return node.snapshot() if node else None

    def snapshots(self) -> list[dict]:
        now = time.time()
        with self._lock:
            nodes = sorted(self._nodes.values(), key=lambda n: ((n.zone or "~").lower(), n.name.lower()))
            return [n.snapshot(now) for n in nodes]

    def remove(self, mac: str) -> None:
        with self._lock:
            self._nodes.pop(mac, None)

    def connection_changes(self) -> list[dict]:
        """Nodos cuyo estado online/stale/offline cambió por paso del tiempo."""
        now = time.time()
        changed = []
        with self._lock:
            for node in self._nodes.values():
                current = node.connection(now)
                if current != node.last_connection:
                    node.last_connection = current
                    changed.append(node.snapshot(now))
        return changed
