import asyncio
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, security
from ..hub import hub
from ..mqtt_service import ALLOWED_COMMANDS, DEVICE_ID_RE, mqtt_service

router = APIRouter(prefix="/devices", tags=["devices"])
viewer = Depends(security.require_role("viewer"))
operator = Depends(security.require_role("operator"))
admin = Depends(security.require_role("admin"))

# Claves de configuración que el firmware sabe interpretar; evita enviar basura a los nodos.
CONFIG_KEYS = {"interval_ms", "reactor_empty_cm", "reactor_full_cm"}


class DevicePatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    zone: Optional[str] = Field(default=None, max_length=80)
    config: Optional[Dict[str, Any]] = None


class CommandIn(BaseModel):
    cmd: str
    params: Dict[str, Any] = Field(default_factory=dict)


def _check_id(device_id: str) -> None:
    if not DEVICE_ID_RE.match(device_id):
        raise HTTPException(422, "device_id debe ser una MAC de 12 hex en minúsculas")


def _merge_live(device: Dict[str, Any]) -> Dict[str, Any]:
    live = hub.live.get(device["device_id"], {})
    return {**device, "live": live}


@router.get("")
async def list_devices(_: Dict[str, Any] = viewer):
    devices = await asyncio.to_thread(db.list_devices)
    return {"devices": [_merge_live(d) for d in devices]}


@router.get("/{device_id}")
async def get_device(device_id: str, _: Dict[str, Any] = viewer):
    _check_id(device_id)
    device = await asyncio.to_thread(db.get_device, device_id)
    if not device:
        raise HTTPException(404, "Dispositivo no encontrado")
    return _merge_live(device)


@router.patch("/{device_id}")
async def patch_device(device_id: str, body: DevicePatch, _: Dict[str, Any] = admin):
    """Asigna nombre/zona/config. Activa el nodo y publica la config retenida por MQTT."""
    _check_id(device_id)
    cfg_patch = None
    if body.config is not None:
        unknown = set(body.config) - CONFIG_KEYS
        if unknown:
            raise HTTPException(422, f"Claves de config no permitidas: {sorted(unknown)}")
        cfg_patch = body.config
    device = await asyncio.to_thread(db.update_device, device_id, body.name, body.zone, cfg_patch)
    if not device:
        raise HTTPException(404, "Dispositivo no encontrado")
    delivered = True
    try:
        await mqtt_service.push_config(device)
    except RuntimeError:
        delivered = False  # se reenviará cuando el nodo vuelva a publicar su meta
    hub.update_live(device_id, {"status": "active"})
    await hub.broadcast({"type": "device_updated", "device_id": device_id})
    return {**_merge_live(device), "config_published": delivered}


@router.post("/{device_id}/cmd", status_code=202)
async def send_command(device_id: str, body: CommandIn, user: Dict[str, Any] = operator):
    _check_id(device_id)
    if body.cmd not in ALLOWED_COMMANDS:
        raise HTTPException(422, f"Comando no permitido. Disponibles: {sorted(ALLOWED_COMMANDS)}")
    device = await asyncio.to_thread(db.get_device, device_id)
    if not device:
        raise HTTPException(404, "Dispositivo no encontrado")
    cmd_id = uuid.uuid4().hex[:12]
    try:
        await mqtt_service.send_command(device_id, {"id": cmd_id, "cmd": body.cmd, **body.params})
    except RuntimeError:
        raise HTTPException(503, "Broker MQTT no disponible")
    await asyncio.to_thread(db.insert_event, device_id, "command", {"id": cmd_id, "cmd": body.cmd, "by": user["username"]})
    return {"id": cmd_id, "status": "sent"}


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: str, _: Dict[str, Any] = admin):
    _check_id(device_id)
    if not await asyncio.to_thread(db.delete_device, device_id):
        raise HTTPException(404, "Dispositivo no encontrado")
    hub.live.pop(device_id, None)
    hub.last_telemetry.pop(device_id, None)
    try:
        await mqtt_service.forget_device(device_id)
    except RuntimeError:
        pass
