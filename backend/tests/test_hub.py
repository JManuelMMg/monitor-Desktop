"""Hub de WebSocket: un cliente lento o caído se cierra (para que reconecte)
en vez de quedarse abierto sin recibir nada."""
import asyncio
import json

from app import hub as hub_module
from app.hub import Hub


class FakeWS:
    def __init__(self, delay: float = 0.0, fail: bool = False) -> None:
        self.delay = delay
        self.fail = fail
        self.sent: list[dict] = []
        self.closed_code: int | None = None

    async def send_text(self, text: str) -> None:
        if self.fail:
            raise RuntimeError("socket roto")
        await asyncio.sleep(self.delay)
        self.sent.append(json.loads(text))

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code


def _run(coro):
    return asyncio.run(coro)


def test_publish_reaches_clients():
    async def scenario():
        hub = Hub()
        await hub.start()
        a, b = FakeWS(), FakeWS()
        hub.add(a)
        hub.add(b)
        hub.publish({"type": "node", "n": 1})
        await asyncio.sleep(0.05)
        await hub.stop()
        return a, b

    a, b = _run(scenario())
    assert a.sent == [{"type": "node", "n": 1}]
    assert b.sent == [{"type": "node", "n": 1}]


def test_failed_send_closes_only_that_client():
    async def scenario():
        hub = Hub()
        await hub.start()
        good, bad = FakeWS(), FakeWS(fail=True)
        hub.add(good)
        hub.add(bad)
        hub.publish({"type": "node"})
        await asyncio.sleep(0.05)
        count = hub.client_count
        await hub.stop()
        return good, bad, count

    good, bad, count = _run(scenario())
    assert bad.closed_code == 1011
    assert good.sent == [{"type": "node"}]
    assert count == 1


def test_slow_client_is_closed_when_queue_fills(monkeypatch):
    monkeypatch.setattr(hub_module, "CLIENT_QUEUE", 3)

    async def scenario():
        hub = Hub()
        await hub.start()
        slow, fast = FakeWS(delay=10), FakeWS()
        hub.add(slow)
        hub.add(fast)
        for i in range(10):
            hub.publish({"type": "node", "n": i})
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        count = hub.client_count
        await hub.stop()
        return slow, fast, count

    slow, fast, count = _run(scenario())
    assert slow.closed_code == 1013
    assert len(fast.sent) == 10
    assert count == 1


def test_heartbeat_tick(monkeypatch):
    monkeypatch.setattr(hub_module, "HEARTBEAT_S", 0.02)

    async def scenario():
        hub = Hub()
        await hub.start()
        ws = FakeWS()
        hub.add(ws)
        await asyncio.sleep(0.08)
        await hub.stop()
        return ws

    ws = _run(scenario())
    assert any(m["type"] == "tick" for m in ws.sent)
