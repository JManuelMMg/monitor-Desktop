from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from .. import db
from ..config import settings
from ..deps import COOKIE_NAME, current_user, invalidate_user
from ..schemas import LoginIn, PasswordChangeIn
from ..security import (DUMMY_HASH, create_access_token, hash_password, login_throttle,
                        password_problems, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def public_user(user: dict) -> dict:
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


def _set_session_cookie(response: Response, request: Request, token: str, max_age: int) -> None:
    response.set_cookie(
        COOKIE_NAME, token, max_age=max_age, httponly=True, samesite="strict", path="/",
        secure=settings.cookie_secure and request.url.scheme == "https",
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    ip = _client_ip(request)
    wait = login_throttle.retry_after(ip, body.username)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Demasiados intentos. Espera {wait} s.", headers={"Retry-After": str(wait)})
    try:
        user = db.get_user_by_username(body.username)
    except db.DatabaseUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Base de datos no disponible")

    valid = verify_password(body.password, user["password_hash"] if user else DUMMY_HASH)
    if not user or not valid or not user["is_active"]:
        login_throttle.failure(ip, body.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")

    login_throttle.success(ip, body.username)
    db.touch_last_login(user["id"])
    token, expires_in = create_access_token(user["id"], user["role"], user["token_version"])
    _set_session_cookie(response, request, token, expires_in)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in,
            "user": public_user(user)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return public_user(user)


@router.post("/password")
def change_password(body: PasswordChangeIn, request: Request, response: Response,
                    user: dict = Depends(current_user)):
    full = db.get_user_by_username(user["username"])
    if not full or not verify_password(body.current_password, full["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    problem = password_problems(body.new_password)
    if problem:
        raise HTTPException(422, problem)
    updated = db.update_user(user["id"], password_hash=hash_password(body.new_password))
    invalidate_user(user["id"])
    # Las demás sesiones quedan invalidadas; esta recibe un token nuevo.
    token, expires_in = create_access_token(updated["id"], updated["role"], updated["token_version"])
    _set_session_cookie(response, request, token, expires_in)
    return {"ok": True, "access_token": token, "expires_in": expires_in}
