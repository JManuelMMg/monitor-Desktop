"""Administración por consola.

    python -m app.cli create-admin             crea un administrador
    python -m app.cli reset-password USER      cambia la contraseña de un usuario
    python -m app.cli list-users
    python -m app.cli init-db                  crea las tablas
    python -m app.cli add-node MAC [--name N] [--zone Z]
                                               alta de nodo o rotación de su clave MQTT;
                                               imprime JSON con la clave (solo esta vez)
    python -m app.cli revoke-node MAC          revoca la clave MQTT del nodo
    python -m app.cli mqtt-sync                regenera el archivo de claves de Mosquitto
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from . import db, mqtt_auth
from .config import settings
from .security import hash_password, password_problems
from .state import default_name
from .topics import normalize_mac


def _ask_password() -> str:
    while True:
        first = getpass.getpass("Contraseña: ")
        problem = password_problems(first)
        if problem:
            print(problem)
            continue
        if getpass.getpass("Repite la contraseña: ") != first:
            print("No coinciden.")
            continue
        return first


def create_admin(_: argparse.Namespace) -> int:
    db.init_schema()
    username = input("Usuario administrador: ").strip()
    if not username:
        print("Usuario vacío.")
        return 1
    if db.get_user_by_username(username):
        print("Ese usuario ya existe; usa reset-password.")
        return 1
    db.create_user(username, hash_password(_ask_password()), "admin")
    print(f"Administrador '{username}' creado.")
    return 0


def reset_password(args: argparse.Namespace) -> int:
    user = db.get_user_by_username(args.username)
    if not user:
        print("Usuario no encontrado.")
        return 1
    db.update_user(user["id"], password_hash=hash_password(_ask_password()), is_active=True)
    print("Contraseña actualizada; sus sesiones abiertas quedaron cerradas.")
    return 0


def list_users(_: argparse.Namespace) -> int:
    for user in db.list_users():
        state = "activo" if user["is_active"] else "inactivo"
        print(f"{user['id']:>4}  {user['username']:<24} {user['role']:<9} {state}")
    return 0


def init_db(_: argparse.Namespace) -> int:
    db.init_schema()
    print("Esquema listo.")
    return 0


def add_node(args: argparse.Namespace) -> int:
    mac = normalize_mac(args.mac)
    if mac is None:
        print("MAC inválida", file=sys.stderr)
        return 1
    db.init_schema()
    if db.get_device(mac) is None:
        db.create_device(mac, args.name or default_name(mac), args.zone, None)
    password = mqtt_auth.issue_credentials(mac)
    if mqtt_auth.last_sync_error:
        print(f"Aviso: no se pudo escribir el archivo de Mosquitto: {mqtt_auth.last_sync_error}", file=sys.stderr)
    print(json.dumps({"mac": mac, "password": password,
                      "mqtt_host": settings.mqtt_public_host or None, "mqtt_port": settings.mqtt_public_port}))
    return 0


def revoke_node(args: argparse.Namespace) -> int:
    mac = normalize_mac(args.mac)
    if mac is None or db.get_device(mac) is None:
        print("Nodo no encontrado", file=sys.stderr)
        return 1
    mqtt_auth.revoke_credentials(mac)
    print(f"Credenciales de {mac} revocadas.")
    return 0


def mqtt_sync(_: argparse.Namespace) -> int:
    db.init_schema()
    if not settings.mqtt_passwd_file:
        print("MQTT_PASSWD_FILE no está configurado", file=sys.stderr)
        return 1
    mqtt_auth.sync_password_file()
    if mqtt_auth.last_sync_error:
        print(f"Error: {mqtt_auth.last_sync_error}", file=sys.stderr)
        return 1
    print(f"Archivo {settings.mqtt_passwd_file} sincronizado.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create-admin").set_defaults(func=create_admin)
    reset = sub.add_parser("reset-password")
    reset.add_argument("username")
    reset.set_defaults(func=reset_password)
    sub.add_parser("list-users").set_defaults(func=list_users)
    sub.add_parser("init-db").set_defaults(func=init_db)
    add = sub.add_parser("add-node")
    add.add_argument("mac")
    add.add_argument("--name")
    add.add_argument("--zone")
    add.set_defaults(func=add_node)
    revoke = sub.add_parser("revoke-node")
    revoke.add_argument("mac")
    revoke.set_defaults(func=revoke_node)
    sub.add_parser("mqtt-sync").set_defaults(func=mqtt_sync)
    args = parser.parse_args()
    try:
        return args.func(args)
    finally:
        db.close_pool()


if __name__ == "__main__":
    sys.exit(main())
