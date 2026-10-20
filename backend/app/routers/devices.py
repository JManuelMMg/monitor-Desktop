from __future__ import annotations

import csv
import io
import uuid

import psycopg2.errors
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from .. import db, mqtt_auth
from ..config import settings
from ..deps import admin, operator, viewer
from ..schemas import CommandIn, DeviceCreate, DevicePatch, NodeConfigIn
from ..security import has_role
from ..services import bridge, hub, registry, writer
from ..topics import normalize_mac

router = APIRouter(prefix="/api", tags=["devices"])


def _mac_or_404(raw: str) -> str:
    mac = normalize_mac(raw)
    if mac is None or registry.get(mac) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nodo no encontrado")
    return mac


def _registered_or_409(mac: str) -> None:
    node = registry.get(mac)
    if node is None or not node.in_db:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "El nodo aún no está guardado en la base; reintenta en unos segundos")


@router.get("/devices")
def list_devices(_: dict = Depends(viewer)):
    return registry.snapshots()


def _credentials(mac: str, password: str) -> dict:
    """La clave en claro solo viaja en esta respuesta; la base guarda el hash."""
    return {
        "username": mac,
        "password": password,
        "mqtt_host": settings.mqtt_public_host or None,
        "mqtt_port": settings.mqtt_public_port,
        "passwd_file_managed": bool(settings.mqtt_passwd_file),
        "passwd_sync_error": mqtt_auth.last_sync_error,
    }


@router.get("/provisioning")
def provisioning_info(_: dict = Depends(admin)):
    return {"mqtt_host": settings.mqtt_public_host or None, "mqtt_port": settings.mqtt_public_port,
            "passwd_file_managed": bool(settings.mqtt_passwd_file)}


@router.post("/devices", status_code=status.HTTP_201_CREATED)
def create_device(body: DeviceCreate, _: dict = Depends(admin)):
    mac = normalize_mac(body.mac)
    if mac is None:
        raise HTTPException(422, "MAC inválida: usa 12 dígitos hexadecimales, p. ej. A4:CF:12:B3:C4:D5")
    existing = registry.get(mac)
    if existing is not None and existing.in_db:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un nodo con la MAC {mac}")
    try:
        db.create_device(mac, body.name.strip(), (body.zone or "").strip() or None,
                         (body.description or "").strip() or None)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un nodo con la MAC {mac}")
    password = mqtt_auth.issue_credentials(mac)
    snapshot = registry.apply_row(db.get_device(mac))
    hub.publish({"type": "node", "node": snapshot})
    return {"node": snapshot, "credentials": _credentials(mac, password)}


@router.post("/devices/{mac}/credentials")
def rotate_credentials(mac: str, _: dict = Depends(admin)):
    mac = _mac_or_404(mac)
    _registered_or_409(mac)
    password = mqtt_auth.issue_credentials(mac)
    snapshot = registry.apply_row(db.get_device(mac))
    hub.publish({"type": "node", "node": snapshot})
    return {"node": snapshot, "credentials": _credentials(mac, password)}


@router.delete("/devices/{mac}/credentials", status_code=status.HTTP_204_NO_CONTENT)
def revoke_credentials(mac: str, _: dict = Depends(admin)):
    mac = _mac_or_404(mac)
    _registered_or_409(mac)
    mqtt_auth.revoke_credentials(mac)
    snapshot = registry.apply_row(db.get_device(mac))
    hub.publish({"type": "node", "node": snapshot})


@router.get("/zones")
def list_zones(_: dict = Depends(viewer)):
    return db.zones()


@router.get("/devices/{mac}")
def get_device(mac: str, _: dict = Depends(viewer)):
    return registry.snapshot(_mac_or_404(mac))


@router.patch("/devices/{mac}")
def update_device(mac: str, body: DevicePatch, user: dict = Depends(operator)):
    mac = _mac_or_404(mac)
    _registered_or_409(mac)
    fields = body.model_dump(exclude_unset=True)
    if "enabled" in fields and not has_role(user["role"], "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo un administrador puede habilitar o deshabilitar nodos")
    if "thresholds" in fields:
        fields["thresholds"] = {k: v for k, v in (fields["thresholds"] or {}).items() if v is not None}
    for key in ("zone", "description"):
        if key in fields and isinstance(fields[key], str):
            fields[key] = fields[key].strip() or None
    if "name" in fields:
        fields["name"] = fields["name"].strip()
    row = db.update_device(mac, fields)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nodo no encontrado")
    snapshot = registry.apply_row(row)
    hub.publish({"type": "node", "node": snapshot})
    return snapshot


@router.put("/devices/{mac}/config")
def set_config(mac: str, body: NodeConfigIn, _: dict = Depends(operator)):
    mac = _mac_or_404(mac)
    _registered_or_409(mac)
    current = registry.get(mac).config
    config = {**body.model_dump(), "rev": int(current.get("rev", 0)) + 1}
    db.update_device(mac, {"config": config})
    snapshot = registry.set_config(mac, config)
    # Retenido: si el nodo está apagado la recibe al reconectar.
    published = bridge.publish_config(mac, config)
    hub.publish({"type": "node", "node": snapshot})
    return {"node": snapshot, "published": published}


@router.post("/devices/{mac}/commands", status_code=status.HTTP_202_ACCEPTED)
def send_command(mac: str, body: CommandIn, user: dict = Depends(operator)):
    mac = _mac_or_404(mac)
    _registered_or_409(mac)
    if not bridge.connected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "El broker MQTT no está disponible")
    args = {"seconds": body.seconds} if body.cmd == "identify" and body.seconds else {}
    cmd_id = str(uuid.uuid4())
    db.insert_command(cmd_id, mac, user["username"], body.cmd, args)
    if not bridge.send_command(mac, cmd_id, body.cmd, args):
        writer.ack(mac, cmd_id, False, "no se pudo publicar en el broker")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No se pudo publicar el comando")
    return {"id": cmd_id, "status": "sent"}


@router.get("/devices/{mac}/commands")
def command_log(mac: str, limit: int = Query(30, ge=1, le=200), _: dict = Depends(viewer)):
    return db.list_commands(_mac_or_404(mac), limit)


@router.get("/devices/{mac}/history")
def history(mac: str, hours: float = Query(24, gt=0, le=24 * 90),
            points: int = Query(300, ge=10, le=2000), _: dict = Depends(viewer)):
    return db.history(_mac_or_404(mac), hours, points)


@router.get("/devices/{mac}/export.csv")
def export_csv(mac: str, hours: float = Query(24, gt=0, le=24 * 90), _: dict = Depends(viewer)):
    mac = _mac_or_404(mac)
    rows = db.export_rows(mac, hours)
    buffer = io.StringIO()
    writer_csv = csv.writer(buffer)
    columns = ["ts", *db.READING_COLUMNS]
    writer_csv.writerow(columns)
    for row in rows:
        writer_csv.writerow([row.get(c) for c in columns])
    name = registry.get(mac).name.replace(" ", "_")
    filename = f"{name}_{mac}_{int(hours)}h.csv".encode("ascii", "ignore").decode()
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/devices/{mac}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(mac: str, _: dict = Depends(admin)):
    mac = _mac_or_404(mac)
    db.delete_device(mac)
    mqtt_auth.sync_password_file()   # sin fila no hay credencial: el nodo ya no entra
    writer.forget(mac)
    registry.remove(mac)
    bridge.clear_retained(mac)
    hub.publish({"type": "removed", "mac": mac})
