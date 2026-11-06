"""Difusión de eventos en vivo a los clientes WebSocket.

Los eventos nacen en el hilo de MQTT; publish() es seguro entre hilos y los
entrega al bucle asyncio de FastAPI.

Cada cliente tiene su propia cola y su propia tarea de envío, así un cliente
lento (WiFi saturada, teléfono en segundo plano) no frena a los demás. Si un
cliente se atrasa o falla un envío, se le CIERRA la conexión: el navegador
reconecta y recibe el estado completo en el mensaje "hello". Antes solo se le
dejaba de enviar, y la página se quedaba congelada mostrando «En vivo».

Además se envía un latido ("tick") cada HEARTBEAT_S para que el navegador
detecte conexiones muertas aunque ningún nodo publique.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import WebSocket

log = logging.getLogger("hub")

HEARTBEAT_S = 15
SEND_TIMEOUT_S = 10
CLIENT_QUEUE = 200


class _Client:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=CLIENT_QUEUE)
        self.task: asyncio.Task | None = None


class Hub:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, _Client] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._heartbeat: asyncio.Task | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._heartbeat = asyncio.create_task(self._beat(), name="ws-heartbeat")

    async def stop(self) -> None:
        if self._heartbeat:
            self._heartbeat.cancel()
        for client in list(self._clients.values()):
            await self._drop(client, code=1001)
        self._clients.clear()
        self._loop = None

    def add(self, ws: WebSocket) -> None:
        client = _Client(ws)
        client.task = asyncio.create_task(self._sender(client), name="ws-sender")
        self._clients[ws] = client

    def remove(self, ws: WebSocket) -> None:
        client = self._clients.pop(ws, None)
        if client and client.task and client.task is not asyncio.current_task():
            client.task.cancel()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def publish(self, event: dict) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._broadcast, event)

    def _broadcast(self, event: dict) -> None:
        if not self._clients:
            return
        message = json.dumps(event, default=str)
        for client in list(self._clients.values()):
            try:
                client.queue.put_nowait(message)
            except asyncio.QueueFull:
                log.warning("Cliente WebSocket atrasado; se cierra para que reconecte")
                self._clients.pop(client.ws, None)
                asyncio.create_task(self._drop(client, code=1013))

    async def _sender(self, client: _Client) -> None:
        try:
            while True:
                message = await client.queue.get()
                await asyncio.wait_for(client.ws.send_text(message), timeout=SEND_TIMEOUT_S)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # timeout, socket cerrado, etc.
            log.info("Envío WebSocket falló (%s); se cierra la conexión", type(exc).__name__)
            self._clients.pop(client.ws, None)
            await self._drop(client, code=1011)

    async def _drop(self, client: _Client, code: int) -> None:
        if client.task and client.task is not asyncio.current_task():
            client.task.cancel()
        try:
            await asyncio.wait_for(client.ws.close(code=code), timeout=3)
        except Exception:
            pass

    async def _beat(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_S)
            self._broadcast({"type": "tick", "ts": time.time()})
