import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db, security

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


def _public(user: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


@router.post("/login")
async def login(body: LoginIn):
    user = await asyncio.to_thread(db.get_user_by_name, body.username.strip())
    # Se verifica siempre contra un hash para no revelar si el usuario existe por tiempo de respuesta.
    hashed = user["password_hash"] if user else security.hash_password("x")
    valid = security.verify_password(hashed, body.password)
    if not user or not valid or not user["active"]:
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    return {**security.create_tokens(user["id"]), "user": _public(user)}


@router.post("/refresh")
async def refresh(body: RefreshIn):
    user_id = security.decode_token(body.refresh_token, "refresh")
    user = await asyncio.to_thread(security.load_user, user_id)
    return {**security.create_tokens(user["id"]), "user": _public(user)}


@router.get("/me")
async def me(user: Dict[str, Any] = Depends(security.current_user)):
    return _public(user)
