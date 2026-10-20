"""Sustituto en memoria de app.db para pruebas sin PostgreSQL."""
from __future__ import annotations

import copy
import itertools
from datetime import datetime, timezone

import psycopg2.errors


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


class FakeDB:
    def __init__(self):
        self.users: dict[int, dict] = {}
        self.devices: dict[str, dict] = {}
        self.readings: list[dict] = []
        self.commands: dict[str, dict] = {}
        self._ids = itertools.count(1)
        self.fail = False

    def _check(self):
        if self.fail:
            from app.db import DatabaseUnavailable
            raise DatabaseUnavailable("caída simulada")

    # infraestructura
    def init_schema(self):
        self._check()

    def close_pool(self):
        pass

    def ping(self):
        return not self.fail

    # usuarios
    def _public(self, u):
        return {k: _iso(v) for k, v in u.items() if k != "password_hash"}

    def count_users(self):
        return len(self.users)

    def count_active_admins(self):
        return sum(1 for u in self.users.values() if u["role"] == "admin" and u["is_active"])

    def get_user_by_username(self, username):
        self._check()
        for u in self.users.values():
            if u["username"].lower() == username.lower():
                return dict(u)
        return None

    def get_user(self, user_id):
        self._check()
        u = self.users.get(user_id)
        return self._public(u) if u else None

    def list_users(self):
        return [self._public(u) for u in sorted(self.users.values(), key=lambda u: u["username"])]

    def create_user(self, username, password_hash, role):
        if self.get_user_by_username(username):
            raise psycopg2.errors.UniqueViolation("duplicado")
        uid = next(self._ids)
        self.users[uid] = {"id": uid, "username": username, "password_hash": password_hash, "role": role,
                           "is_active": True, "token_version": 0, "created_at": _now(), "last_login": None}
        return self._public(self.users[uid])

    def update_user(self, user_id, *, role=None, is_active=None, password_hash=None):
        u = self.users.get(user_id)
        if not u:
            return None
        changed = False
        for key, value in (("role", role), ("is_active", is_active), ("password_hash", password_hash)):
            if value is not None:
                u[key] = value
                changed = True
        if changed:
            u["token_version"] += 1
        return self._public(u)

    def delete_user(self, user_id):
        return self.users.pop(user_id, None) is not None

    def touch_last_login(self, user_id):
        self.users[user_id]["last_login"] = _now()

    # dispositivos
    def _dev(self, d):
        out = {k: _iso(v) for k, v in copy.deepcopy(d).items() if k != "mqtt_password_hash"}
        out["has_credentials"] = bool(d.get("mqtt_password_hash"))
        out.setdefault("credentials_issued_at", None)
        return out

    def create_device(self, mac, name, zone, description):
        if mac in self.devices:
            raise psycopg2.errors.UniqueViolation("duplicado")
        self.devices[mac] = {
            "mac": mac, "name": name, "zone": zone, "description": description, "enabled": True,
            "config": {}, "thresholds": {}, "fw_version": None, "last_ip": None, "first_seen": _now(),
            "last_seen": None, "mqtt_password_hash": None, "credentials_issued_at": None,
        }
        return self._dev(self.devices[mac])

    def set_mqtt_credentials(self, mac, password_hash):
        d = self.devices.get(mac)
        if not d:
            return False
        d["mqtt_password_hash"] = password_hash
        d["credentials_issued_at"] = _now() if password_hash else None
        return True

    def list_mqtt_credentials(self):
        return [{"mac": m, "mqtt_password_hash": d["mqtt_password_hash"]}
                for m, d in self.devices.items() if d.get("mqtt_password_hash")]

    def list_devices(self):
        self._check()
        return [self._dev(d) for d in self.devices.values()]

    def get_device(self, mac):
        d = self.devices.get(mac)
        return self._dev(d) if d else None

    def upsert_seen(self, entries):
        self._check()
        for e in entries:
            d = self.devices.get(e["mac"])
            if d is None:
                self.devices[e["mac"]] = {
                    "mac": e["mac"], "name": e["name"], "zone": None, "description": None, "enabled": True,
                    "config": {}, "thresholds": {}, "fw_version": e.get("fw_version"),
                    "last_ip": e.get("last_ip"), "first_seen": _now(), "last_seen": e["last_seen"],
                }
            else:
                d["last_seen"] = e["last_seen"]
                d["fw_version"] = e.get("fw_version") or d["fw_version"]
                d["last_ip"] = e.get("last_ip") or d["last_ip"]

    def update_device(self, mac, fields):
        self._check()
        d = self.devices.get(mac)
        if not d:
            return None
        d.update(copy.deepcopy(fields))
        return self._dev(d)

    def delete_device(self, mac):
        self.readings = [r for r in self.readings if r["mac"] != mac]
        return self.devices.pop(mac, None) is not None

    def zones(self):
        return sorted({d["zone"] for d in self.devices.values() if d["zone"]})

    # lecturas
    def insert_readings(self, rows):
        self._check()
        for r in rows:
            assert r["mac"] in self.devices, "clave foránea"
            if not any(x["mac"] == r["mac"] and x["ts"] == r["ts"] for x in self.readings):
                self.readings.append(dict(r))

    def history(self, mac, hours, max_points):
        return [{**{k: v for k, v in r.items() if k != "mac"}, "ts": _iso(r["ts"])}
                for r in self.readings if r["mac"] == mac]

    def export_rows(self, mac, hours):
        return self.history(mac, hours, 0)

    def purge_readings(self, days):
        return 0

    # comandos
    def insert_command(self, cmd_id, mac, username, cmd, args):
        self.commands[cmd_id] = {"id": cmd_id, "mac": mac, "username": username, "cmd": cmd, "args": args,
                                 "sent_at": _now(), "ok": None, "response": None, "acked_at": None}

    def ack_commands(self, acks):
        for a in acks:
            c = self.commands.get(a["id"])
            if c and c["mac"] == a["mac"]:
                c.update(ok=a["ok"], response=a["msg"], acked_at=a["ts"])

    def list_commands(self, mac, limit=30):
        rows = [c for c in self.commands.values() if c["mac"] == mac]
        rows.sort(key=lambda c: c["sent_at"], reverse=True)
        return [{k: _iso(v) for k, v in c.items()} for c in rows[:limit]]


FUNCTIONS = [name for name in dir(FakeDB) if not name.startswith("_") and name != "fail"]
