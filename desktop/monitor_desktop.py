"""App de escritorio Windows del monitor multi-nodo.

Es una ventana nativa (WebView2 de Windows vía pywebview, sin Node/Electron)
que abre la interfaz servida por la Raspberry Pi. Prueba los servidores en
orden — primero la red local, luego la IP de la VPN WireGuard — y cambia
solo de uno a otro si el actual deja de responder.

Configuración: %APPDATA%\\MonitorMultiNodo\\config.json
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import webview

APP_NAME = "MonitorMultiNodo"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_CONFIG = {
    # Orden de preferencia: LAN primero, VPN después.
    "servers": ["https://192.168.1.50:8443", "https://10.8.0.1:8443"],
    "check_interval_s": 20,
}
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("desktop")


def load_config() -> dict:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return {**DEFAULT_CONFIG, **data}
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def ssl_context() -> ssl.SSLContext:
    # create_default_context carga el almacén de certificados de Windows,
    # el mismo que usa WebView2. La CA de la Pi debe estar importada ahí
    # (instalar_ca.ps1); un ca.crt junto al ejecutable también se acepta
    # para la comprobación de conectividad.
    ctx = ssl.create_default_context()
    bundled = RESOURCE_DIR / "ca.crt"
    if bundled.is_file():
        ctx.load_verify_locations(cafile=str(bundled))
    return ctx


def normalize_server(url: str) -> str | None:
    url = url.strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.netloc or parts.path or parts.query:
        return None
    return url


def probe(url: str, timeout: float = 3.0) -> bool:
    request = urllib.request.Request(url + "/healthz", headers={"User-Agent": APP_NAME})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context()) as response:
            return response.status == 200 and json.load(response).get("ok") is True
    except (urllib.error.URLError, OSError, ValueError, ssl.SSLError) as exc:
        log.info("Sin respuesta de %s: %s", url, exc)
        return False


def pick_server(servers: list[str]) -> str | None:
    for url in servers:
        if probe(url):
            return url
    return None


class Bridge:
    """API expuesta a setup.html y lógica de conmutación LAN/VPN."""

    def __init__(self) -> None:
        self.config = load_config()
        self.current: str | None = None
        self.window: webview.Window | None = None

    # --- llamados desde JavaScript (setup.html) ---
    def get_config(self) -> dict:
        return {"servers": self.config["servers"], "config_file": str(CONFIG_FILE)}

    def save_servers(self, servers: list[str]) -> dict:
        cleaned = []
        for raw in servers:
            url = normalize_server(str(raw))
            if url is None:
                return {"ok": False, "error": f"Dirección inválida: {raw}"}
            if url not in cleaned:
                cleaned.append(url)
        if not cleaned:
            return {"ok": False, "error": "Indica al menos un servidor"}
        self.config["servers"] = cleaned
        save_config(self.config)
        return {"ok": True}

    def retry(self) -> dict:
        url = pick_server(self.config["servers"])
        if url is None:
            return {"ok": False, "error": "Ningún servidor respondió. Revisa la red, la VPN o el certificado."}
        self._open(url)
        return {"ok": True, "url": url}

    # --- interno ---
    def _open(self, url: str) -> None:
        self.current = url
        log.info("Usando servidor %s", url)
        if self.window:
            self.window.load_url(url + "/")

    def watch(self) -> None:
        """Si el servidor actual cae (p. ej. al salir de casa), prueba los
        demás y cambia a la VPN sin intervención."""
        while True:
            time.sleep(max(5, int(self.config.get("check_interval_s", 20))))
            if self.current and probe(self.current):
                continue
            url = pick_server(self.config["servers"])
            if url and url != self.current:
                self._open(url)
            elif url is None and self.current:
                log.warning("Ningún servidor disponible")
                self.current = None
                if self.window:
                    self.window.load_url((RESOURCE_DIR / "setup.html").as_uri() + "?offline=1")


def main() -> None:
    bridge = Bridge()
    if not CONFIG_FILE.exists():
        save_config(bridge.config)
    start_url = pick_server(bridge.config["servers"])
    bridge.current = start_url
    target = start_url + "/" if start_url else (RESOURCE_DIR / "setup.html").as_uri()
    bridge.window = webview.create_window(
        "Monitor multi-nodo", target, js_api=bridge, width=1360, height=880, min_size=(960, 640),
    )
    threading.Thread(target=bridge.watch, daemon=True).start()
    # Sesión persistente (cookie HttpOnly) entre aperturas de la app.
    webview.start(private_mode=False, storage_path=str(CONFIG_DIR / "webview"))


if __name__ == "__main__":
    main()
