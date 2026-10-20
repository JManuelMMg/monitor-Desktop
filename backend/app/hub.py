"""Difusión de eventos en vivo a los clientes WebSocket.

Los eventos nacen en el hilo de MQTT; publish() es seguro entre hilos y los
entrega al bucle asyncio de FastAPI.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket

log = logging.getLogger("hub")


class Hub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=2000)
        self._task = asyncio.create_task(self._run(), name="ws-hub")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        for client in list(self._clients):
            try:
                await client.close()
            except Exception:
                pass
        self._clients.clear()
        self._loop = None

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def publish(self, event: dict) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._enqueue, event)

    def _enqueue(self, event: dict) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            log.warning("Cola de WebSocket llena; evento descartado")

    async def _run(self) -> None:
        while True:
            event = await self._queue.get()
            if not self._clients:
                continue
            message = json.dumps(event, default=str)
            clients = list(self._clients)
            results = await asyncio.gather(
                *(asyncio.wait_for(c.send_text(message), timeout=2) for c in clients),
                return_exceptions=True,
            )
            for client, result in zip(clients, results):
                if isinstance(result, BaseException):
                    self._clients.discard(client)
