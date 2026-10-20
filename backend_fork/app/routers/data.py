import asyncio
import csv
import io
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from .. import db, security
from ..hub import hub
from ..mqtt_service import DEVICE_ID_RE, mqtt_service

router = APIRouter(tags=["data"])
viewer = Depends(security.require_role("viewer"))


def _check(device_id: Optional[str]) -> None:
    if device_id is not None and not DEVICE_ID_RE.match(device_id):
        raise HTTPException(422, "device_id inválido")


@router.get("/health")
async def health():
    return {"status": "ok", "mqtt": mqtt_service.connected}


@router.get("/live")
async def live(_: Dict[str, Any] = viewer):
    return hub.snapshot()


@router.get("/history")
async def history(device_id: Optional[str] = None, hours: float = Query(24, gt=0, le=24 * 30),
                  limit: int = Query(5000, gt=0, le=50000), _: Dict[str, Any] = viewer):
    _check(device_id)
    return {"history": await asyncio.to_thread(db.get_history, device_id, hours, limit)}


@router.get("/events")
async def events(device_id: Optional[str] = None, limit: int = Query(100, gt=0, le=1000),
                 _: Dict[str, Any] = viewer):
    _check(device_id)
    return {"events": await asyncio.to_thread(db.list_events, device_id, limit)}


@router.get("/export")
async def export_csv(device_id: Optional[str] = None, hours: float = Query(24, gt=0, le=24 * 30),
                     _: Dict[str, Any] = viewer):
    _check(device_id)
    rows = await asyncio.to_thread(db.get_history, device_id, hours, 50000)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["device_id", "ts_utc", "temp_c", "hum_pct", "ch4_ppm", "co2_ppm", "dist_cm", "level_pct"])
    for r in rows:
        writer.writerow([r["device_id"], r["ts"], r["temp"], r["hum"], r["ch4_ppm"],
                         r["co2_ppm"], r["dist_cm"], r["level_pct"]])
    return StreamingResponse(
        io.BytesIO(out.getvalue().encode("utf-8")), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lecturas_{hours:g}h.csv"},
    )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    """Telemetría en vivo. Autenticación por ?token=<access_token>."""
    try:
        user = await asyncio.to_thread(lambda: security.load_user(security.decode_token(token, "access")))
    except Exception:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub.clients.add(websocket)
    try:
        await websocket.send_json({**hub.snapshot(), "mqtt": mqtt_service.connected, "role": user["role"]})
        while True:
            await websocket.receive_text()  # ping/keep-alive del cliente
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(websocket)
