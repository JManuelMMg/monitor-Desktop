"""Callbacks del puente con objetos reales de paho-mqtt 2.x."""
import json

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from app.hub import Hub
from app.mqtt_bridge import MqttBridge
from app.state import Registry


class FakeWriter:
    def __init__(self):
        self.seen_calls, self.readings, self.acks = [], [], []

    def seen(self, mac, name, fw=None, ip=None):
        self.seen_calls.append((mac, fw, ip))

    def reading(self, mac, data, ts):
        self.readings.append((mac, data))

    def ack(self, mac, cmd_id, ok, msg):
        self.acks.append((mac, cmd_id, ok, msg))


class FakeClient:
    def __init__(self):
        self.subscriptions = []

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))


def message(topic: str, payload) -> mqtt.MQTTMessage:
    msg = mqtt.MQTTMessage(topic=topic.encode())
    msg.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return msg


def make_bridge():
    hub = Hub()
    events = []
    hub.publish = events.append
    writer = FakeWriter()
    return MqttBridge(Registry(), hub, writer), writer, events


def test_on_connect_subscribes_and_handles_refusal():
    bridge, _, events = make_bridge()
    client = FakeClient()
    bridge._on_connect(client, None, None, ReasonCode(PacketTypes.CONNACK, "Not authorized"), None)
    assert not bridge.connected and client.subscriptions == []
    bridge._on_connect(client, None, None, ReasonCode(PacketTypes.CONNACK, "Success"), None)
    assert bridge.connected
    assert client.subscriptions == [("monitor/v1/nodes/+/#", 1)]
    assert events[-1] == {"type": "broker", "connected": True}
    bridge._on_disconnect(client, None, None, ReasonCode(PacketTypes.DISCONNECT, "Normal disconnection"), None)
    assert not bridge.connected


def test_on_message_routes_and_filters():
    bridge, writer, events = make_bridge()
    base = "monitor/v1/nodes/a4cf12b3c4d5"
    bridge._on_message(None, None, message(f"{base}/status", {"state": "online", "fw": "3.0.0", "ip": "10.0.0.9"}))
    bridge._on_message(None, None, message(f"{base}/telemetry", {"temp_c": 22.5, "co2_ok": True}))
    assert writer.readings and writer.readings[0][1]["temp_c"] == 22.5
    assert ("a4cf12b3c4d5", "3.0.0", "10.0.0.9") in writer.seen_calls

    count = len(events)
    bridge._on_message(None, None, message(f"{base}/telemetry", b"no-json"))
    bridge._on_message(None, None, message(f"{base}/telemetry", b"[1,2]"))
    bridge._on_message(None, None, message(f"{base}/telemetry", b"x" * 5000))
    bridge._on_message(None, None, message(f"{base}/status", b""))                 # retenido borrado
    bridge._on_message(None, None, message("monitor/v1/nodes/ZZ/telemetry", {"temp_c": 1}))
    bridge._on_message(None, None, message(f"{base}/cmd", {"id": "x", "cmd": "reboot"}))  # saliente: ignorar
    assert len(events) == count

    bridge._on_message(None, None, message(f"{base}/cmd/ack", {"id": "no-uuid", "ok": True}))
    assert writer.acks == []
    bridge._on_message(None, None, message(f"{base}/cmd/ack",
                                           {"id": "6f1c2a8e-9d4b-4f0e-8a51-0c2b6f3d7e11", "cmd": "ping", "ok": True, "msg": "pong"}))
    assert writer.acks[-1][2:] == (True, "pong")

    bridge._on_message(None, None, message(f"{base}/event", {
        "type": "mq4_calibration", "id": "6f1c2a8e-9d4b-4f0e-8a51-0c2b6f3d7e11", "ok": True, "r0_kohm": 12.3456}))
    assert "12.346" in writer.acks[-1][3]
