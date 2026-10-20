"""Cliente MQTT del backend: consume tópicos de los nodos y publica config/comandos."""
import asyncio
import json
import logging
import re
import ssl
import time
from typing import Any, Dict, Optional

import aiomqtt

from . import config, db, store
from .hub import hub

log = logging.getLogger("mqtt")
DEVICE_ID_RE = re.compile(r"^[0-9a-f]{12}$")
ALLOWED_COMMANDS = {"reboot", "calibrate_mq4", "calibrate_co2_zero", "relay"}


def device_topic(device_id: str, leaf: str) -> str:
    return f"{config.MQTT_ROOT}/{device_id}/{leaf}"


def build_node_config(device: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(device.get("config") or {})
    cfg["name"] = device.get("name") or ""
    cfg["zone"] = device.get("zone") or ""
    return cfg


class MqttService:
    def __init__(self) -> None:
        self._client: Optional[aiomqtt.Client] = None
        self.connected = False

    # ----- publicación -----
    async def publish(self, topic: str, payload: Any, qos: int = 1, retain: bool = False) -> None:
        if self._client is None or not self.connected:
            raise RuntimeError("Broker MQTT no disponible")
        data = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
        await self._client.publish(topic, data, qos=qos, retain=retain)

    async def push_config(self, device: Dict[str, Any]) -> None:
        await self.publish(device_topic(device["device_id"], "config"),
                           build_node_config(device), qos=1, retain=True)

    async def send_command(self, device_id: str, cmd: Dict[str, Any]) -> None:
        await self.publish(device_topic(device_id, "cmd"), cmd, qos=1, retain=False)

    async def forget_device(self, device_id: str) -> None:
        """Borra los mensajes retenidos del nodo en el broker."""
        for leaf in ("config", "meta", "status"):
            await self.publish(device_topic(device_id, leaf), b"", qos=1, retain=True)

    # ----- bucle principal -----
    async def run(self) -> None:
        delay = 1
        while True:
            try:
                tls = None
                if config.MQTT_TLS:
                    tls = ssl.create_default_context(cafile=config.MQTT_CA_FILE or None)
                async with aiomqtt.Client(
                    hostname=config.MQTT_HOST, port=config.MQTT_PORT,
                    username=config.MQTT_USER or None, password=config.MQTT_PASSWORD or None,
                    identifier="monitor-backend", tls_context=tls, keepalive=30,
                ) as client:
                    self._client = client
                    self.connected = True
                    delay = 1
                    await client.subscribe(f"{config.MQTT_ROOT}/+/#", qos=1)
                    log.info("Conectado al broker %s:%s", config.MQTT_HOST, config.MQTT_PORT)
                    await hub.broadcast({"type": "backend", "mqtt": True})
                    async for message in client.messages:
                        try:
                            await self._dispatch(str(message.topic), bytes(message.payload or b""))
                        except Exception:
                            log.exception("Error procesando %s", message.topic)
            except aiomqtt.MqttError as exc:
                log.warning("MQTT desconectado: %s (reintento en %ss)", exc, delay)
            finally:
                self.connected = False
                self._client = None
            await hub.broadcast({"type": "backend", "mqtt": False})
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)

    # ----- enrutado -----
    async def _dispatch(self, topic: str, payload: bytes) -> None:
        parts = topic.split("/")
        # monitor/v1/{id}/{leaf...}
        if len(parts) < 4 or "/".join(parts[:2]) != config.MQTT_ROOT:
            return
        device_id, leaf = parts[2], "/".join(parts[3:])
        if not DEVICE_ID_RE.match(device_id) or not payload:
            return
        if leaf in ("config", "cmd"):
            return  # eco de nuestras propias publicaciones
        if leaf == "status":
            await self._on_status(device_id, payload.decode(errors="ignore").strip())
            return
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            log.debug("JSON inválido en %s", topic)
            return
        if not isinstance(data, dict):
            return
        if leaf == "meta":
            await self._on_meta(device_id, data)
        elif leaf == "telemetry":
            await self._on_telemetry(device_id, data)
        elif leaf in ("event", "cmd/ack"):
            await self._on_event(device_id, "ack" if leaf == "cmd/ack" else "event", data)

    async def _on_meta(self, device_id: str, meta: Dict[str, Any]) -> None:
        device = await asyncio.to_thread(db.upsert_device_meta, device_id, meta)
        hub.update_live(device_id, {"fw": device["fw"], "ip": device["ip"], "rssi": device["rssi"],
                                    "sensors": device["sensors"], "status": device["status"]})
        if device["status"] == "pending":
            await asyncio.to_thread(db.insert_event, device_id, "discovered", meta)
            await hub.broadcast({"type": "discovered", "device_id": device_id})
        else:
            # Reasegura la config retenida por si el broker perdió su persistencia.
            await self.push_config(device)

    async def _on_status(self, device_id: str, state: str) -> None:
        online = state == "online"
        await asyncio.to_thread(db.ensure_device, device_id)
        await asyncio.to_thread(db.set_device_online, device_id, online)
        hub.update_live(device_id, {"online": online})
        await hub.broadcast({"type": "status", "device_id": device_id, "online": online})
        log.info("Nodo %s %s", device_id, "online" if online else "offline")

    async def _on_telemetry(self, device_id: str, data: Dict[str, Any]) -> None:
        hub.touch(device_id)
        if device_id not in hub.live:
            await asyncio.to_thread(db.ensure_device, device_id)  # requerido por la FK
        entry = hub.update_live(device_id, {**data, "online": True, "received_at": time.time()})
        await hub.broadcast({"type": "telemetry", "device_id": device_id, "data": entry})
        await store.save(device_id, data)

    async def _on_event(self, device_id: str, kind: str, data: Dict[str, Any]) -> None:
        await asyncio.to_thread(db.ensure_device, device_id)
        await asyncio.to_thread(db.insert_event, device_id, kind, data)
        await hub.broadcast({"type": kind, "device_id": device_id, "data": data})


mqtt_service = MqttService()


async def watchdog() -> None:
    """Marca como caídos los nodos sin telemetría y sube el búfer pendiente."""
    while True:
        await asyncio.sleep(5)
        now = time.monotonic()
        for device_id, seen in list(hub.last_telemetry.items()):
            entry = hub.live.get(device_id)
            if entry and entry.get("online") and now - seen > config.OFFLINE_AFTER_S:
                entry["online"] = False
                try:
                    await asyncio.to_thread(db.set_device_online, device_id, False)
                except Exception:
                    log.debug("No se pudo marcar offline %s", device_id)
                await hub.broadcast({"type": "status", "device_id": device_id, "online": False})
        await store.flush_buffer()
