"""Puente entre Mosquitto y el backend (paho-mqtt en su propio hilo)."""
from __future__ import annotations

import json
import logging
import ssl
import time
import uuid

import paho.mqtt.client as mqtt

from . import topics
from .config import settings
from .hub import Hub
from .persistence import Writer
from .state import Registry, normalize_telemetry

log = logging.getLogger("mqtt")

MAX_PAYLOAD = 4096


def _is_uuid(value: object) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


class MqttBridge:
    def __init__(self, registry: Registry, hub: Hub, writer: Writer) -> None:
        self.registry = registry
        self.hub = hub
        self.writer = writer
        self.connected = False
        self._client: mqtt.Client | None = None

    def start(self) -> None:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="monitor-backend",
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        if settings.mqtt_username:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password or None)
        if settings.mqtt_tls_ca:
            client.tls_set(ca_certs=settings.mqtt_tls_ca, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=30)
        client.loop_start()
        self._client = client

    def stop(self) -> None:
        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
            self._client = None
        self.connected = False

    # ---------------------------------------------------------- callbacks
    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            log.error("Mosquitto rechazó la conexión: %s", reason_code)
            return
        self.connected = True
        client.subscribe(topics.SUBSCRIPTION, qos=1)
        log.info("Conectado a Mosquitto %s:%s", settings.mqtt_host, settings.mqtt_port)
        self.hub.publish({"type": "broker", "connected": True})

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        self.connected = False
        log.warning("Desconectado de Mosquitto: %s", reason_code)
        self.hub.publish({"type": "broker", "connected": False})

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage) -> None:
        parsed = topics.parse(msg.topic)
        if parsed is None or len(msg.payload) > MAX_PAYLOAD:
            return
        if not msg.payload:
            return  # retenido borrado
        try:
            payload = json.loads(msg.payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            log.warning("JSON inválido en %s", msg.topic)
            return
        if not isinstance(payload, dict):
            return
        mac, kind = parsed
        try:
            self._dispatch(mac, kind, payload)
        except Exception:
            log.exception("Error procesando %s", msg.topic)

    def _dispatch(self, mac: str, kind: str, payload: dict) -> None:
        if kind == topics.TELEMETRY:
            data = normalize_telemetry(payload)
            snapshot, node, created = self.registry.on_telemetry(mac, data)
            self.writer.seen(mac, node.name, node.status.get("fw"), node.status.get("ip"))
            if node.enabled:
                self.writer.reading(mac, data, time.time())
            if created:
                log.info("Nodo nuevo detectado: %s", topics.format_mac(mac))
            self.hub.publish({"type": "node", "node": snapshot})

        elif kind == topics.STATUS:
            snapshot, node, created = self.registry.on_status(mac, payload)
            if node.online:
                self.writer.seen(mac, node.name, payload.get("fw"), payload.get("ip"))
            if created:
                log.info("Nodo nuevo detectado: %s", topics.format_mac(mac))
            self.hub.publish({"type": "node", "node": snapshot})

        elif kind == topics.CONFIG_STATE:
            snapshot = self.registry.on_config_state(mac, payload)
            self.hub.publish({"type": "node", "node": snapshot})

        elif kind == topics.CMD_ACK:
            cmd_id = payload.get("id")
            if not _is_uuid(cmd_id):
                return
            ok = payload.get("ok") is True
            msg = str(payload.get("msg", ""))[:500]
            self.writer.ack(mac, str(cmd_id), ok, msg)
            self.hub.publish({"type": "ack", "mac": mac, "id": cmd_id, "cmd": payload.get("cmd"),
                              "ok": ok, "msg": msg})

        elif kind == topics.EVENT:
            self.hub.publish({"type": "event", "mac": mac, "event": payload})
            if payload.get("type") == "mq4_calibration" and _is_uuid(payload.get("id")):
                ok = payload.get("ok") is True
                detail = (f"calibración completada, R0 = {payload.get('r0_kohm'):.3f} kΩ"
                          if ok and isinstance(payload.get("r0_kohm"), (int, float))
                          else str(payload.get("msg", "calibración fallida")))
                self.writer.ack(mac, str(payload["id"]), ok, detail)

    # ---------------------------------------------------------- publicación
    def _publish(self, topic: str, payload: str, retain: bool) -> bool:
        if not self._client or not self.connected:
            return False
        info = self._client.publish(topic, payload, qos=1, retain=retain)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    def send_command(self, mac: str, cmd_id: str, cmd: str, args: dict) -> bool:
        body = json.dumps({"id": cmd_id, "cmd": cmd, "args": args})
        return self._publish(topics.node_topic(mac, topics.CMD), body, retain=False)

    def publish_config(self, mac: str, config: dict) -> bool:
        return self._publish(topics.node_topic(mac, topics.CONFIG_SET), json.dumps(config), retain=True)

    def clear_retained(self, mac: str) -> None:
        for kind in (topics.CONFIG_SET, topics.STATUS, topics.CONFIG_STATE):
            self._publish(topics.node_topic(mac, kind), "", retain=True)
