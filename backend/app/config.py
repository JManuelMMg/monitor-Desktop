"""Configuración leída del entorno.

En la Raspberry Pi las variables vienen de /etc/monitor/monitor.env a través
de systemd (EnvironmentFile). En desarrollo se lee backend/.env con un
parser mínimo para no añadir dependencias.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        # Las variables del entorno real (systemd, shell) tienen prioridad,
        # salvo que estén vacías.
        if not os.environ.get(key.strip()):
            os.environ[key.strip()] = value


# En la Pi: MONITOR_ENV_FILE=/etc/monitor/monitor.env (lo usa deploy/pi/monitor-cli.sh).
_load_dotenv(Path(os.getenv("MONITOR_ENV_FILE") or BASE_DIR.parent / ".env"))


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


def _origins(name: str) -> tuple[str, ...]:
    """Lista de orígenes https://host:puerto separados por comas."""
    out = []
    for raw in os.getenv(name, "").split(","):
        value = raw.strip().rstrip("/")
        if re.fullmatch(r"https?://[A-Za-z0-9.\-\[\]:]+", value) and value not in out:
            out.append(value)
    return tuple(out)


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    db_pool_max: int = field(default_factory=lambda: _int("DB_POOL_MAX", 5))
    db_schema: str = field(default_factory=lambda: os.getenv("DB_SCHEMA", "monitor"))

    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    access_token_minutes: int = field(default_factory=lambda: _int("ACCESS_TOKEN_MINUTES", 720))
    cookie_secure: bool = field(default_factory=lambda: _bool("COOKIE_SECURE", True))

    mqtt_host: str = field(default_factory=lambda: os.getenv("MQTT_HOST", "127.0.0.1"))
    mqtt_port: int = field(default_factory=lambda: _int("MQTT_PORT", 1883))
    mqtt_username: str = field(default_factory=lambda: os.getenv("MQTT_USERNAME", "backend"))
    mqtt_password: str = field(default_factory=lambda: os.getenv("MQTT_PASSWORD", ""))
    mqtt_tls_ca: str = field(default_factory=lambda: os.getenv("MQTT_TLS_CA", ""))
    # Archivo password_file de Mosquitto que mantiene el backend (vacío = no se escribe).
    mqtt_passwd_file: str = field(default_factory=lambda: os.getenv("MQTT_PASSWD_FILE", ""))
    # Dirección y puerto a los que se conectan los ESP32 (para la línea de aprovisionamiento).
    mqtt_public_host: str = field(default_factory=lambda: os.getenv("MQTT_PUBLIC_HOST", ""))
    mqtt_public_port: int = field(default_factory=lambda: _int("MQTT_PUBLIC_PORT", 8883))

    # Cada cuánto se guarda una lectura por nodo (el WebSocket recibe todas).
    persist_interval_s: float = field(default_factory=lambda: _float("PERSIST_INTERVAL_S", 10))
    # Cada cuánto se vacía el lote hacia Neon. Más alto = menos tiempo de
    # cómputo en Neon, más datos en memoria si el proceso cae.
    db_flush_interval_s: float = field(default_factory=lambda: _float("DB_FLUSH_INTERVAL_S", 15))
    retention_days: int = field(default_factory=lambda: _int("RETENTION_DAYS", 180))
    spool_dir: Path = field(default_factory=lambda: Path(os.getenv("SPOOL_DIR", str(BASE_DIR.parent / "data"))))
    spool_max_mb: int = field(default_factory=lambda: _int("SPOOL_MAX_MB", 50))

    # Un nodo sin telemetría durante este tiempo pasa a "stale".
    stale_after_s: float = field(default_factory=lambda: _float("STALE_AFTER_S", 30))

    # Direcciones por las que se llega a este mismo servidor (LAN, VPN…). La
    # web las usa para cambiar de una a otra si la actual deja de responder.
    public_urls: tuple = field(default_factory=lambda: _origins("PUBLIC_URLS"))

    debug: bool = field(default_factory=lambda: _bool("DEBUG", False))

    def validate(self) -> list[str]:
        problems = []
        if len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET debe tener al menos 32 caracteres")
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", self.db_schema):
            problems.append("DB_SCHEMA debe ser un identificador en minúsculas (letras, números, _)")
        if not self.database_url:
            problems.append("DATABASE_URL no está configurada")
        return problems


settings = Settings()
