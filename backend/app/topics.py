"""Contrato de tópicos MQTT (debe coincidir con firmware/esp32_node).

    monitor/v1/nodes/<mac>/status        nodo -> backend  retenido + LWT
    monitor/v1/nodes/<mac>/telemetry     nodo -> backend
    monitor/v1/nodes/<mac>/event         nodo -> backend
    monitor/v1/nodes/<mac>/cmd           backend -> nodo  QoS 1
    monitor/v1/nodes/<mac>/cmd/ack       nodo -> backend
    monitor/v1/nodes/<mac>/config/set    backend -> nodo  retenido, QoS 1
    monitor/v1/nodes/<mac>/config/state  nodo -> backend  retenido

<mac> son 12 dígitos hexadecimales en minúscula, sin separadores. El nombre
y la zona NO forman parte del tópico: viven en la base de datos, así que
mover un nodo de sitio no cambia nada en el broker ni en el firmware.
"""
from __future__ import annotations

import re

ROOT = "monitor/v1/nodes"
SUBSCRIPTION = f"{ROOT}/+/#"

STATUS = "status"
TELEMETRY = "telemetry"
EVENT = "event"
CMD = "cmd"
CMD_ACK = "cmd/ack"
CONFIG_SET = "config/set"
CONFIG_STATE = "config/state"

INBOUND = {STATUS, TELEMETRY, EVENT, CMD_ACK, CONFIG_STATE}

MAC_RE = re.compile(r"^[0-9a-f]{12}$")


def normalize_mac(value: str) -> str | None:
    """Acepta 'A4:CF:12:B3:C4:D5', 'a4-cf-...' o 'a4cf12b3c4d5'."""
    mac = re.sub(r"[^0-9a-fA-F]", "", value or "").lower()
    return mac if MAC_RE.match(mac) else None


def node_topic(mac: str, kind: str) -> str:
    if not MAC_RE.match(mac):
        raise ValueError(f"MAC inválida: {mac!r}")
    return f"{ROOT}/{mac}/{kind}"


def parse(topic: str) -> tuple[str, str] | None:
    """Devuelve (mac, tipo) para tópicos entrantes válidos, o None."""
    prefix = ROOT + "/"
    if not topic.startswith(prefix):
        return None
    rest = topic[len(prefix):]
    mac, _, kind = rest.partition("/")
    if not MAC_RE.match(mac) or kind not in INBOUND:
        return None
    return mac, kind


def format_mac(mac: str) -> str:
    return ":".join(mac[i:i + 2] for i in range(0, 12, 2)).upper()
