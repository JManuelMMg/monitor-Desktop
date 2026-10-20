import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, security
from .mqtt_service import mqtt_service, watchdog
from .routers import auth, data, devices, users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


def _bootstrap() -> None:
    db.init_schema()
    if db.count_users() == 0:
        if not config.ADMIN_PASSWORD:
            log.warning("No hay usuarios y ADMIN_PASSWORD está vacío: define ADMIN_PASSWORD y reinicia.")
            return
        db.create_user(config.ADMIN_USER, security.hash_password(config.ADMIN_PASSWORD), "admin")
        log.info("Administrador inicial '%s' creado", config.ADMIN_USER)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(config.JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres")
    await asyncio.to_thread(_bootstrap)
    tasks = [asyncio.create_task(mqtt_service.run()), asyncio.create_task(watchdog())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        db.close()


app = FastAPI(title="Monitor Multi-Nodo - Backend Raspberry Pi", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"],
    allow_credentials=False,
)
app.include_router(data.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(devices.router)
