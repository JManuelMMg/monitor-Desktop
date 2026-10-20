"""Credenciales MQTT de los nodos y archivo de contraseñas de Mosquitto.

El backend es la única fuente de verdad: guarda el hash de la clave de cada
nodo en la base y regenera el archivo `password_file` de Mosquitto
(MQTT_PASSWD_FILE). En la Pi, una unidad systemd .path detecta el cambio y
recarga Mosquitto (deploy/systemd/mosquitto-monitor-reload.*).

Formato compatible con Mosquitto 2.x (mosquitto_passwd):
    usuario:$7$<iteraciones>$<sal base64>$<PBKDF2-HMAC-SHA512 base64>
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import threading
from pathlib import Path

from . import db
from .config import settings

log = logging.getLogger("mqtt_auth")

ITERATIONS = 20000
SALT_LEN = 12
_lock = threading.Lock()
_backend_line: str | None = None
last_sync_error: str | None = None


def generate_password() -> str:
    # 32 caracteres alfanuméricos: fáciles de pegar en el monitor serie.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(32))


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(SALT_LEN)
    digest = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), salt, iterations)
    return f"$7${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    """Misma comprobación que hace Mosquitto (usada en pruebas)."""
    try:
        _, kind, iterations, salt, digest = encoded.split("$")
        if kind != "7":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), base64.b64decode(salt), int(iterations))
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(actual, expected)


def _backend_entry() -> str | None:
    """La clave del usuario 'backend' sale del entorno; su hash se calcula
    una vez por proceso para que el archivo no cambie en cada escritura."""
    global _backend_line
    if _backend_line is None and settings.mqtt_username and settings.mqtt_password:
        _backend_line = f"{settings.mqtt_username}:{hash_password(settings.mqtt_password)}"
    return _backend_line


def render(entries: list[dict]) -> str:
    lines = []
    backend = _backend_entry()
    if backend:
        lines.append(backend)
    for entry in sorted(entries, key=lambda e: e["mac"]):
        if entry.get("mqtt_password_hash"):
            lines.append(f"{entry['mac']}:{entry['mqtt_password_hash']}")
    return "\n".join(lines) + "\n"


def sync_password_file() -> bool:
    """Reescribe el archivo de Mosquitto si cambió. Devuelve True si escribió.
    Sin MQTT_PASSWD_FILE (desarrollo en Windows) no hace nada. Un error de
    disco queda en last_sync_error en vez de romper la petición."""
    global last_sync_error
    path_value = settings.mqtt_passwd_file
    if not path_value:
        return False
    path = Path(path_value)
    with _lock:
        content = render(db.list_mqtt_credentials())
        try:
            try:
                if path.read_text(encoding="utf-8") == content:
                    last_sync_error = None
                    return False
            except FileNotFoundError:
                pass
            tmp = path.with_name(f".{path.name}.tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            # El directorio tiene setgid: el archivo hereda el grupo mosquitto.
            os.replace(tmp, path)
        except OSError as exc:
            last_sync_error = str(exc)
            log.error("No se pudo escribir %s: %s", path, exc)
            return False
        last_sync_error = None
        log.info("Archivo de credenciales MQTT actualizado (%d líneas)", content.count("\n"))
        return True


def issue_credentials(mac: str) -> str:
    """Genera (o rota) la clave MQTT del nodo y devuelve la clave en claro.
    Solo se muestra una vez: en la base queda el hash."""
    password = generate_password()
    db.set_mqtt_credentials(mac, hash_password(password))
    sync_password_file()
    return password


def revoke_credentials(mac: str) -> None:
    db.set_mqtt_credentials(mac, None)
    sync_password_file()
