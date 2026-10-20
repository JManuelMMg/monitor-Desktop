"""Servidor de demostración SIN base de datos ni broker: base en memoria y
nodos simulados. Sirve para revisar la interfaz en desarrollo.

    .venv\\Scripts\\python.exe tests\\demo_server.py
    -> http://127.0.0.1:8765  (usuario demo / demo-demo-demo)

- 6 nodos enviando datos (uno deja de enviar a los 40 s y otro está en alarma).
- 1 nodo registrado que nunca se conecta ("Esperando conexión").
- Los nodos que crees con «Agregar nodo» se conectan solos a los ~8 s.
"""
import math
import os
import random
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update({
    "JWT_SECRET": "demo-" + "x" * 40, "DATABASE_URL": "postgresql://demo/demo",
    "COOKIE_SECURE": "false", "PERSIST_INTERVAL_S": "5", "DB_FLUSH_INTERVAL_S": "2",
    "SPOOL_DIR": tempfile.mkdtemp(prefix="monitor-demo-"), "MQTT_PUBLIC_HOST": "192.168.1.50",
    # Dos nombres del mismo servidor local para probar la página Conexión.
    "PUBLIC_URLS": "http://localhost:8765,http://127.0.0.1:8765",
})

import uvicorn  # noqa: E402

from app import db, services, topics  # noqa: E402
from app.security import hash_password  # noqa: E402
from tests.fake_db import FUNCTIONS, FakeDB  # noqa: E402

fake = FakeDB()
for name in FUNCTIONS:
    setattr(db, name, getattr(fake, name))
fake.create_user("demo", hash_password("demo-demo-demo"), "admin")

services.bridge.start = lambda: setattr(services.bridge, "connected", True)
services.bridge.stop = lambda: None


def echo(topic, payload, retain):
    """Responde como lo haría el firmware a config/set y cmd."""
    import json
    parts = topic.split("/")
    mac, kind = parts[3], "/".join(parts[4:])

    def later():
        time.sleep(0.6)
        if kind == topics.CONFIG_SET and payload:
            services.bridge._dispatch(mac, topics.CONFIG_STATE, json.loads(payload))
        elif kind == topics.CMD:
            cmd = json.loads(payload)
            services.bridge._dispatch(mac, topics.CMD_ACK, {"id": cmd["id"], "cmd": cmd["cmd"], "ok": True,
                                                             "msg": "pong" if cmd["cmd"] == "ping" else "hecho (demo)"})
    threading.Thread(target=later, daemon=True).start()
    return True


services.bridge._publish = echo

NODES = [("a4cf12b3c4d1", "Biodigestor 1", "Granja norte"), ("a4cf12b3c4d2", "Biodigestor 2", "Granja norte"),
         ("a4cf12b3c4d3", "Reactor piloto", "Laboratorio"), ("a4cf12b3c4d4", "Biodigestor 3", "Granja sur"),
         ("a4cf12b3c4d5", "Tanque de lodos", "Granja sur"), ("a4cf12b3c4d6", None, None)]
for mac, name, zone in NODES:
    fake.create_device(mac, name or f"Nodo {mac[-4:].upper()}", zone, None)
    fake.set_mqtt_credentials(mac, "$7$demo")
fake.create_device("a4cf12b3c4e0", "Biodigestor 4", "Granja sur", "Recién instalado")
fake.set_mqtt_credentials("a4cf12b3c4e0", "$7$demo")


def telemetry(seq, t, i):
    return {
        "seq": seq, "up": int(t), "rssi": -52 - i * 5,
        "temp_c": round(31 + i * 1.5 + 2 * math.sin(t / 60 + i), 1),
        "hum_pct": round(62 + 10 * math.sin(t / 90 + i), 1),
        "ch4_ppm": round(1500 + 500 * math.sin(t / 45 + i) + (4200 if i == 2 else 0) + random.uniform(-40, 40)),
        "co2_ppm": round(900 + 150 * math.sin(t / 70 + i)),
        "dist_cm": round(40 + 10 * math.sin(t / 120 + i), 1),
        "level_pct": round(55 + 25 * math.sin(t / 120 + i), 1),
        "dht_ok": True, "co2_ok": True, "mq_warm": True, "mq_cal": i != 3, "mq_ok": i != 3, "us_ok": True,
    }


def simulate():
    time.sleep(1.5)
    start = time.time()
    for i, (mac, _, _) in enumerate(NODES):
        services.bridge._dispatch(mac, topics.STATUS, {"state": "online", "fw": "3.0.0", "ip": f"192.168.1.{60 + i}"})
        services.bridge._dispatch(mac, topics.CONFIG_STATE, {"rev": 0, "interval_ms": 5000})
    seq = 0
    while True:
        seq += 1
        t = time.time() - start
        for i, (mac, _, _) in enumerate(NODES):
            if i == 5 and t > 40:
                continue  # este nodo deja de enviar: pasa a «sin datos»
            services.bridge._dispatch(mac, topics.TELEMETRY, telemetry(seq, t, i))
        # Nodos creados desde el asistente: se «conectan» a los 8 s.
        for mac, dev in list(fake.devices.items()):
            if mac in {m for m, _, _ in NODES} or mac == "a4cf12b3c4e0" or not dev.get("mqtt_password_hash"):
                continue
            if time.time() - dev["first_seen"].timestamp() > 8:
                services.bridge._dispatch(mac, topics.STATUS, {"state": "online", "fw": "3.0.0", "ip": "192.168.1.99"})
                services.bridge._dispatch(mac, topics.TELEMETRY, telemetry(seq, t, 1))
        time.sleep(2)


threading.Thread(target=simulate, daemon=True).start()
uvicorn.run("app.main:app", host="127.0.0.1", port=8765, log_level="warning")
