"""Estado en vivo y difusión a clientes WebSocket."""
import asyncio
import json
import time
from typing import Any, Dict, Set

from fastapi import WebSocket


class Hub:
    def __init__(self) -> None:
        self.clients: Set[WebSocket] = set()
        self.live: Dict[str, Dict[str, Any]] = {}
        self.last_telemetry: Dict[str, float] = {}

    def snapshot(self) -> Dict[str, Any]:
        return {"type": "snapshot", "devices": self.live}

    def update_live(self, device_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        entry = self.live.setdefault(device_id, {"device_id": device_id})
        entry.update(patch)
        return entry

    def touch(self, device_id: str) -> None:
        self.last_telemetry[device_id] = time.monotonic()

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self.clients:
            return
        text = json.dumps(message, default=str)
        clients = list(self.clients)
        results = await asyncio.gather(
            *(asyncio.wait_for(c.send_text(text), timeout=1.0) for c in clients),
            return_exceptions=True,
        )
        for client, result in zip(clients, results):
            if isinstance(result, BaseException):
                self.clients.discard(client)


hub = Hub()
