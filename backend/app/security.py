"""Contraseñas (scrypt de la biblioteca estándar) y tokens JWT firmados."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

import jwt

from .config import settings

ROLES = ("viewer", "operator", "admin")
ROLE_RANK = {role: rank for rank, role in enumerate(ROLES)}

_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM, dklen=32,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=base64.b64decode(salt_b64),
            n=int(n), r=int(r), p=int(p), maxmem=_SCRYPT_MAXMEM, dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


# Hash fijo para gastar el mismo tiempo cuando el usuario no existe y no
# revelar qué nombres de usuario son válidos.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def password_problems(password: str) -> str | None:
    if len(password) < 10:
        return "La contraseña debe tener al menos 10 caracteres"
    if len(password) > 128:
        return "La contraseña no puede superar 128 caracteres"
    return None


def create_access_token(user_id: int, role: str, token_version: int) -> tuple[str, int]:
    now = int(time.time())
    expires_in = settings.access_token_minutes * 60
    payload = {
        "sub": str(user_id),
        "role": role,
        "ver": token_version,
        "iat": now,
        "exp": now + expires_in,
        "iss": "monitor-backend",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expires_in


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=["HS256"], issuer="monitor-backend",
            options={"require": ["sub", "exp", "iat", "ver"]},
        )
    except jwt.PyJWTError:
        return None


def has_role(role: str, minimum: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK[minimum]


class LoginThrottle:
    """Bloquea temporalmente IP+usuario tras varios intentos fallidos."""

    def __init__(self, max_failures: int = 5, window_s: int = 900, lockout_s: int = 900):
        self.max_failures = max_failures
        self.window_s = window_s
        self.lockout_s = lockout_s
        self._failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._locked_until: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def retry_after(self, ip: str, username: str) -> int:
        key = (ip, username.lower())
        with self._lock:
            until = self._locked_until.get(key, 0)
            remaining = until - time.monotonic()
            if remaining <= 0:
                self._locked_until.pop(key, None)
                return 0
            return int(remaining) + 1

    def failure(self, ip: str, username: str) -> None:
        key = (ip, username.lower())
        now = time.monotonic()
        with self._lock:
            attempts = self._failures[key]
            attempts.append(now)
            while attempts and now - attempts[0] > self.window_s:
                attempts.popleft()
            if len(attempts) >= self.max_failures:
                self._locked_until[key] = now + self.lockout_s
                attempts.clear()

    def success(self, ip: str, username: str) -> None:
        key = (ip, username.lower())
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)


login_throttle = LoginThrottle()
