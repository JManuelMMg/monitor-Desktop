"""WebSocket de datos en vivo: /ws

Autenticación: la cookie de sesión (navegador / app de escritorio) o, si no
hay cookie, un primer mensaje {"type": "auth", "token": "<jwt>"} en menos de
5 s. El token nunca va en la URL para que no quede en logs.
"""
from __future__ import annotations

import asyncio
import json
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..deps import COOKIE_NAME, authenticate_token
from ..services import bridge, hub, registry

router = APIRouter()


def _same_origin(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin")
    if not origin:
        return True  # clientes que no son navegador
    return urlsplit(origin).netloc == ws.headers.get("host")


@router.websocket("/ws")
async def live(ws: WebSocket):
    if not _same_origin(ws):
        await ws.close(code=1008)
        return
    user = None
    cookie = ws.cookies.get(COOKIE_NAME)
    if cookie:
        user = await asyncio.to_thread(authenticate_token, cookie)
    await ws.accept()
    if user is None:
        try:
            first = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=5))
            if first.get("type") == "auth" and isinstance(first.get("token"), str):
                user = await asyncio.to_thread(authenticate_token, first["token"])
        except (asyncio.TimeoutError, json.JSONDecodeError, AttributeError, WebSocketDisconnect):
            user = None
    if user is None:
        await ws.close(code=4401)
        return

    await ws.send_text(json.dumps({
        "type": "hello",
        "user": {"username": user["username"], "role": user["role"]},
        "broker": bridge.connected,
        "nodes": registry.snapshots(),
    }, default=str))
    hub.add(ws)
    try:
        while True:
            await ws.receive_text()  # ping del cliente; no se esperan otros mensajes
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(ws)
