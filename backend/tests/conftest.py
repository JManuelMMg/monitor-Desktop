import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.update({
    "JWT_SECRET": "x" * 48,
    "DATABASE_URL": "postgresql://fake/fake",
    "DB_FLUSH_INTERVAL_S": "0.05",
    "PERSIST_INTERVAL_S": "0",
    "COOKIE_SECURE": "false",
    "SPOOL_DIR": tempfile.mkdtemp(prefix="monitor-spool-"),
})

from fastapi.testclient import TestClient  # noqa: E402

from app import db, services  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_password  # noqa: E402
from tests.fake_db import FUNCTIONS, FakeDB  # noqa: E402

FAKE = FakeDB()
for _name in FUNCTIONS:
    setattr(db, _name, getattr(FAKE, _name))


class PublishRecorder:
    def __init__(self):
        self.messages = []

    def __call__(self, topic, payload, retain):
        self.messages.append((topic, payload, retain))
        return True


RECORDER = PublishRecorder()
services.bridge.start = lambda: None
services.bridge.stop = lambda: None
services.bridge._publish = RECORDER


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        services.bridge.connected = True
        yield c


@pytest.fixture
def fake():
    FAKE.fail = False
    return FAKE


@pytest.fixture
def recorder():
    RECORDER.messages.clear()
    return RECORDER


def make_user(username, role, password="contraseña-segura"):
    existing = FAKE.get_user_by_username(username)
    if existing:
        return existing
    return FAKE.create_user(username, hash_password(password), role)


def login(client, username, password="contraseña-segura"):
    client.cookies.clear()
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def wait_for(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False
