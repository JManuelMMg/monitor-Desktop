"""Instancias compartidas del proceso (un solo worker de uvicorn)."""
from __future__ import annotations

import logging

from . import db, mqtt_auth
from .hub import Hub
from .mqtt_bridge import MqttBridge
from .persistence import Writer
from .state import Registry

log = logging.getLogger("services")

registry = Registry()
hub = Hub()


def _load_devices() -> None:
    rows = db.list_devices()
    registry.load(rows)
    log.info("%d nodos cargados desde la base", len(rows))
    mqtt_auth.sync_password_file()
    for snapshot in registry.snapshots():
        hub.publish({"type": "node", "node": snapshot})


writer = Writer(on_db_ready=_load_devices, on_registered=registry.mark_registered)
bridge = MqttBridge(registry, hub, writer)
