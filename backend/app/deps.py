"""Dependencias de autenticación y autorización.

Se acepta el JWT de dos formas:
- Cabecera Authorization: Bearer <token> (clientes de API, scripts).
- Cookie HttpOnly SameSite=Strict (interfaz web y app de escritorio). Para
  métodos que modifican estado con cookie se exige además la cabecera
  X-CSRF: 1, que un formulario de otro sitio no puede enviar.
"""
from __future__ import annotations

import threading
import time

from fastapi import Depends, HTTPException, Request, status

from . import db
from .security import decode_access_token, has_role

COOKIE_NAME = "monitor_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
USER_CACHE_TTL_S = 10

_cache: dict[int, tuple[float, dict | None]] = {}
_cache_lock = threading.Lock()


def invalidate_user(user_id: int) -> None:
    with _cache_lock:
        _cache.pop(user_id, None)


def _load_user(user_id: int) -> dict | None:
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(user_id)
        if cached and now - cached[0] < USER_CACHE_TTL_S:
            return cached[1]
    user = db.get_user(user_id)
    with _cache_lock:
        _cache[user_id] = (now, user)
    return user


def authenticate_token(token: str) -> dict | None:
    claims = decode_access_token(token)
    if not claims:
        return None
    try:
        user = _load_user(int(claims["sub"]))
    except (ValueError, db.DatabaseUnavailable):
        return None
    if not user or not user["is_active"] or user["token_version"] != claims.get("ver"):
        return None
    return user


def _extract_token(request: Request) -> tuple[str | None, bool]:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip(), False
    return request.cookies.get(COOKIE_NAME), True


def optional_user(request: Request) -> dict | None:
    token, _ = _extract_token(request)
    return authenticate_token(token) if token else None


def current_user(request: Request) -> dict:
    token, from_cookie = _extract_token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado",
                            headers={"WWW-Authenticate": "Bearer"})
    if from_cookie and request.method not in SAFE_METHODS and request.headers.get("x-csrf") != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Falta la cabecera X-CSRF")
    user = authenticate_token(token)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require(minimum: str):
    def dependency(user: dict = Depends(current_user)) -> dict:
        if not has_role(user["role"], minimum):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permisos insuficientes")
        return user
    return dependency


viewer = require("viewer")
operator = require("operator")
admin = require("admin")
