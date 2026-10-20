"""Backend del sistema de monitoreo (Raspberry Pi).

Arranque en desarrollo:
    python -m uvicorn app.main:app --port 8000
En la Pi lo lanza systemd (deploy/systemd/monitor-backend.service) con TLS.
Debe correr con UN solo worker: el estado en vivo y el puente MQTT viven en
memoria de este proceso.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import BASE_DIR, settings
from .routers import auth, devices, live, pages, system, users
from .services import bridge, hub, registry, writer

logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


async def _watch_connections() -> None:
    """Marca nodos como stale/offline cuando dejan de enviar datos."""
    while True:
        await asyncio.sleep(5)
        for snapshot in registry.connection_changes():
            hub.publish({"type": "node", "node": snapshot})


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = settings.validate()
    if problems:
        raise RuntimeError("Configuración incompleta: " + "; ".join(problems))
    await hub.start()
    writer.start()
    bridge.start()
    watcher = asyncio.create_task(_watch_connections())
    log.info("Backend iniciado")
    try:
        yield
    finally:
        watcher.cancel()
        bridge.stop()
        writer.stop()
        await asyncio.to_thread(writer.join, 30)
        await hub.stop()
        db.close_pool()


app = FastAPI(
    title="Monitor multi-nodo",
    lifespan=lifespan,
    # Swagger UI carga recursos de un CDN; solo se habilita en desarrollo.
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# connect-src incluye las otras direcciones del propio servidor (PUBLIC_URLS)
# para poder comprobar cuál responde y cambiar de LAN a VPN sin recargar.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       f"connect-src 'self' {' '.join(settings.public_urls)}; worker-src 'self'; manifest-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/docs"):
        response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(db.DatabaseUnavailable)
async def database_unavailable(request: Request, exc: db.DatabaseUnavailable):
    log.error("Base de datos no disponible: %s", exc)
    return JSONResponse({"detail": "Base de datos no disponible"}, status_code=503)


@app.get("/healthz", include_in_schema=False)
def healthz(response: Response):
    # Público y sin cookies: lo consultan la app de escritorio y la web desde
    # otra dirección del mismo servidor (LAN ↔ VPN) para saber cuál responde.
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True, "service": "monitor-multinodo", "mqtt": bridge.connected, "db": writer.db_ok}


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(devices.router)
app.include_router(system.router)
app.include_router(live.router)
app.include_router(pages.router)
