import asyncio
from typing import Any, Dict, Literal, Optional

import psycopg2.errors
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, security

router = APIRouter(prefix="/users", tags=["users"])
Role = Literal["admin", "operator", "viewer"]
admin = Depends(security.require_role("admin"))


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=10, max_length=128)
    role: Role = "viewer"


class UserPatch(BaseModel):
    password: Optional[str] = Field(default=None, min_length=10, max_length=128)
    role: Optional[Role] = None
    active: Optional[bool] = None


@router.get("")
async def list_users(_: Dict[str, Any] = admin):
    return {"users": await asyncio.to_thread(db.list_users)}


@router.post("", status_code=201)
async def create_user(body: UserIn, _: Dict[str, Any] = admin):
    password_hash = security.hash_password(body.password)
    try:
        return await asyncio.to_thread(db.create_user, body.username.strip(), password_hash, body.role)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(409, "Ese usuario ya existe")


@router.patch("/{user_id}")
async def patch_user(user_id: int, body: UserPatch, me: Dict[str, Any] = admin):
    target = await asyncio.to_thread(db.get_user, user_id)
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    demotes = (body.role is not None and body.role != "admin") or body.active is False
    if target["role"] == "admin" and target["active"] and demotes:
        if await asyncio.to_thread(db.count_active_admins) <= 1:
            raise HTTPException(409, "Debe quedar al menos un administrador activo")
    fields: Dict[str, Any] = {}
    if body.password is not None:
        fields["password_hash"] = security.hash_password(body.password)
    if body.role is not None:
        fields["role"] = body.role
    if body.active is not None:
        fields["active"] = body.active
    return await asyncio.to_thread(db.update_user, user_id, fields)


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, me: Dict[str, Any] = admin):
    target = await asyncio.to_thread(db.get_user, user_id)
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    if target["role"] == "admin" and target["active"]:
        if await asyncio.to_thread(db.count_active_admins) <= 1:
            raise HTTPException(409, "Debe quedar al menos un administrador activo")
    await asyncio.to_thread(db.delete_user, user_id)
