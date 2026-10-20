from __future__ import annotations

import psycopg2.errors
from fastapi import APIRouter, Depends, HTTPException, status

from .. import db
from ..deps import admin, invalidate_user
from ..schemas import UserCreate, UserPatch
from ..security import hash_password, password_problems

router = APIRouter(prefix="/api/users", tags=["users"])


def _check_password(password: str) -> None:
    problem = password_problems(password)
    if problem:
        raise HTTPException(422, problem)


def _would_remove_last_admin(target: dict, new_role: str | None, new_active: bool | None) -> bool:
    if target["role"] != "admin" or not target["is_active"]:
        return False
    loses_admin = (new_role is not None and new_role != "admin") or new_active is False
    return loses_admin and db.count_active_admins() <= 1


@router.get("")
def list_users(_: dict = Depends(admin)):
    return db.list_users()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _: dict = Depends(admin)):
    _check_password(body.password)
    try:
        return db.create_user(body.username, hash_password(body.password), body.role)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese nombre de usuario ya existe")


@router.patch("/{user_id}")
def update_user(user_id: int, body: UserPatch, _: dict = Depends(admin)):
    target = db.get_user(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if _would_remove_last_admin(target, body.role, body.is_active):
        raise HTTPException(status.HTTP_409_CONFLICT, "Debe quedar al menos un administrador activo")
    password_hash = None
    if body.password:
        _check_password(body.password)
        password_hash = hash_password(body.password)
    updated = db.update_user(user_id, role=body.role, is_active=body.is_active, password_hash=password_hash)
    invalidate_user(user_id)
    return updated


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, me: dict = Depends(admin)):
    if user_id == me["id"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "No puedes eliminar tu propio usuario")
    target = db.get_user(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if _would_remove_last_admin(target, None, False):
        raise HTTPException(status.HTTP_409_CONFLICT, "Debe quedar al menos un administrador activo")
    db.delete_user(user_id)
    invalidate_user(user_id)
