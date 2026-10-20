import json
import time

from app import services, topics
from tests.conftest import login, make_user, wait_for

MAC = "a4cf12b3c4d5"
CSRF = {"X-CSRF": "1"}


def feed_node(mac=MAC, temp=24.0):
    # El reloj de Windows tiene ~15 ms de resolución; (mac, ts) es único.
    time.sleep(0.03)
    services.bridge._dispatch(mac, topics.STATUS, {"state": "online", "fw": "3.0.0", "ip": "192.168.1.60"})
    services.bridge._dispatch(mac, topics.TELEMETRY, {
        "seq": 1, "up": 100, "rssi": -60, "temp_c": temp, "hum_pct": 50, "ch4_ppm": 120,
        "co2_ppm": 800, "dist_cm": 40, "level_pct": 66.7, "dht_ok": True, "co2_ok": True,
        "mq_warm": True, "mq_cal": True, "mq_ok": True, "us_ok": True,
    })


def test_pages_require_login(client):
    client.cookies.clear()
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/login"
    page = client.get("/login")
    assert page.status_code == 200 and "Contraseña" in page.text
    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert client.get("/api/devices").status_code == 401


def test_healthz(client):
    body = client.get("/healthz").json()
    assert body["ok"] is True and "mqtt" in body and "db" in body


def test_login_cookie_and_csrf(client, fake):
    make_user("admin", "admin")
    client.cookies.clear()
    raw = client.post("/api/auth/login", json={"username": "admin", "password": "contraseña-segura"})
    cookie = raw.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    data = raw.json()
    assert data["user"]["role"] == "admin"
    assert client.get("/api/auth/me").json()["username"] == "admin"
    # Con cookie, un POST sin X-CSRF se rechaza.
    assert client.post("/api/users", json={"username": "zz", "password": "x" * 12}).status_code == 403
    # Con Bearer no hace falta X-CSRF.
    client.cookies.clear()
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert res.status_code == 200


def test_login_throttle(client, fake):
    make_user("lento", "viewer")
    client.cookies.clear()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "lento", "password": "mala"}).status_code == 401
    res = client.post("/api/auth/login", json={"username": "lento", "password": "contraseña-segura"})
    assert res.status_code == 429 and "Retry-After" in res.headers


def test_auto_registration_and_persistence(client, fake):
    feed_node()
    assert wait_for(lambda: MAC in fake.devices and any(r["mac"] == MAC for r in fake.readings))
    device = fake.devices[MAC]
    assert device["name"] == "Nodo C4D5" and device["fw_version"] == "3.0.0"
    assert wait_for(lambda: services.registry.get(MAC).in_db)
    login(client, "admin")
    node = client.get(f"/api/devices/{MAC}").json()
    assert node["connection"] == "online" and node["telemetry"]["co2_ppm"] == 800
    assert node["registered"] is True


def test_roles_on_device_patch(client, fake):
    feed_node()
    wait_for(lambda: services.registry.get(MAC).in_db)
    make_user("vera", "viewer")
    make_user("oscar", "operator")

    login(client, "vera")
    assert client.patch(f"/api/devices/{MAC}", json={"name": "X"}, headers=CSRF).status_code == 403

    login(client, "oscar")
    res = client.patch(f"/api/devices/{MAC}", json={"name": "Biodigestor 1", "zone": "Patio norte"}, headers=CSRF)
    assert res.status_code == 200 and res.json()["zone"] == "Patio norte"
    assert fake.devices[MAC]["name"] == "Biodigestor 1"
    assert client.patch(f"/api/devices/{MAC}", json={"enabled": False}, headers=CSRF).status_code == 403
    assert client.patch(f"/api/devices/{MAC}", json={"bogus": 1}, headers=CSRF).status_code == 422
    assert client.get("/api/zones").json() == ["Patio norte"]


def test_config_is_published_retained(client, fake, recorder):
    feed_node()
    wait_for(lambda: services.registry.get(MAC).in_db)
    login(client, "oscar")
    config = {"interval_ms": 10000, "dht_temp_offset": -0.5, "dht_hum_offset": 2, "us_offset_cm": 1,
              "us_scale": 1.0, "reactor_empty_cm": 120, "reactor_full_cm": 15, "co2_abc": False, "status_led": True}
    bad = client.put(f"/api/devices/{MAC}/config", json={**config, "reactor_full_cm": 200}, headers=CSRF)
    assert bad.status_code == 422
    res = client.put(f"/api/devices/{MAC}/config", json=config, headers=CSRF)
    assert res.status_code == 200 and res.json()["published"] is True
    topic, payload, retain = recorder.messages[-1]
    assert topic == f"monitor/v1/nodes/{MAC}/config/set" and retain is True
    sent = json.loads(payload)
    assert sent["interval_ms"] == 10000 and sent["rev"] >= 1
    assert res.json()["node"]["config_pending"] is True
    services.bridge._dispatch(MAC, topics.CONFIG_STATE, sent)
    assert client.get(f"/api/devices/{MAC}").json()["config_pending"] is False


def test_command_and_ack(client, fake, recorder):
    feed_node()
    wait_for(lambda: services.registry.get(MAC).in_db)
    login(client, "oscar")
    res = client.post(f"/api/devices/{MAC}/commands", json={"cmd": "identify", "seconds": 5}, headers=CSRF)
    assert res.status_code == 202
    cmd_id = res.json()["id"]
    topic, payload, retain = recorder.messages[-1]
    assert topic == f"monitor/v1/nodes/{MAC}/cmd" and retain is False
    assert json.loads(payload) == {"id": cmd_id, "cmd": "identify", "args": {"seconds": 5}}
    assert client.post(f"/api/devices/{MAC}/commands", json={"cmd": "rm -rf"}, headers=CSRF).status_code == 422

    services.bridge._dispatch(MAC, topics.CMD_ACK, {"id": cmd_id, "cmd": "identify", "ok": True, "msg": "LED"})
    assert wait_for(lambda: fake.commands[cmd_id]["ok"] is True)
    log = client.get(f"/api/devices/{MAC}/commands").json()
    assert log[0]["id"] == cmd_id and log[0]["response"] == "LED"


def test_websocket_receives_live_updates(client, fake):
    feed_node()
    login(client, "vera")
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and any(n["mac"] == MAC for n in hello["nodes"])
        feed_node(temp=31.5)
        while True:
            event = ws.receive_json()
            if event["type"] == "node" and (event["node"]["telemetry"] or {}).get("temp_c") == 31.5:
                break


def test_websocket_rejects_anonymous_and_foreign_origin(client):
    client.cookies.clear()
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": "falso"}))
        try:
            ws.receive_json()
            raise AssertionError("debió cerrarse")
        except Exception as exc:
            assert "4401" in repr(exc) or "WebSocketDisconnect" in type(exc).__name__


def test_user_management_rules(client, fake):
    admin = make_user("admin", "admin")
    login(client, "admin")
    res = client.post("/api/users", json={"username": "nuevo", "password": "corta", "role": "viewer"}, headers=CSRF)
    assert res.status_code == 422
    res = client.post("/api/users", json={"username": "nuevo", "password": "suficientemente-larga", "role": "viewer"},
                      headers=CSRF)
    assert res.status_code == 201
    assert client.post("/api/users", json={"username": "NUEVO", "password": "suficientemente-larga"},
                       headers=CSRF).status_code == 409
    # No se puede quitar el último administrador ni borrarse a sí mismo.
    for user in fake.users.values():
        if user["role"] == "admin" and user["id"] != admin["id"]:
            user["is_active"] = False
    assert client.patch(f"/api/users/{admin['id']}", json={"role": "viewer"}, headers=CSRF).status_code == 409
    assert client.delete(f"/api/users/{admin['id']}", headers=CSRF).status_code == 409


def test_password_change_revokes_old_tokens(client, fake):
    make_user("pablo", "viewer")
    old = login(client, "pablo")["access_token"]
    res = client.post("/api/auth/password", json={"current_password": "contraseña-segura",
                                                   "new_password": "otra-contraseña-larga"}, headers=CSRF)
    assert res.status_code == 200
    assert client.get("/api/auth/me").status_code == 200       # cookie renovada
    client.cookies.clear()
    from app import deps
    deps.invalidate_user(fake.get_user_by_username("pablo")["id"])
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_spool_when_database_down(client, fake):
    feed_node()
    wait_for(lambda: services.registry.get(MAC).in_db)
    before = len([r for r in fake.readings if r["mac"] == MAC])
    fake.fail = True
    feed_node(temp=20.1)
    assert wait_for(lambda: services.writer.spool_path.exists())
    assert not services.writer.db_ok
    fake.fail = False
    assert wait_for(lambda: not services.writer.spool_path.exists() and services.writer.db_ok)
    after = [r for r in fake.readings if r["mac"] == MAC]
    assert len(after) > before and any(r["temp_c"] == 20.1 for r in after)


def test_disabled_node_is_not_persisted(client, fake):
    other = "0011223344aa"
    feed_node(other)
    assert wait_for(lambda: other in fake.devices)
    login(client, "admin")
    assert client.patch(f"/api/devices/{other}", json={"enabled": False}, headers=CSRF).status_code == 200
    count = len([r for r in fake.readings if r["mac"] == other])
    feed_node(other, temp=99)
    services.writer.flush()
    assert len([r for r in fake.readings if r["mac"] == other]) == count
    assert client.get(f"/api/devices/{other}").json()["alarms"] == []


def test_delete_device_clears_retained(client, fake, recorder):
    other = "0011223344bb"
    feed_node(other)
    assert wait_for(lambda: other in fake.devices and services.registry.get(other).in_db)
    login(client, "admin")
    assert client.delete(f"/api/devices/{other}", headers=CSRF).status_code == 204
    assert other not in fake.devices
    cleared = {t for t, p, r in recorder.messages if p == "" and r}
    assert f"monitor/v1/nodes/{other}/config/set" in cleared
    assert client.get(f"/api/devices/{other}").status_code == 404


def test_node_pages_render(client, fake):
    feed_node()
    login(client, "vera")
    page = client.get(f"/nodes/{MAC}")
    assert page.status_code == 200 and f'data-mac="{MAC}"' in page.text
    assert client.get("/admin", follow_redirects=False).status_code == 303
    login(client, "admin")
    assert client.get("/admin").status_code == 200
    assert client.get("/static/js/node.js").status_code == 200


def test_add_node_from_panel_issues_mqtt_credentials(client, fake, tmp_path, monkeypatch):
    from app import mqtt_auth
    from app.config import settings
    passwd = tmp_path / "passwd"
    monkeypatch.setattr(settings.__class__, "mqtt_passwd_file", property(lambda self: str(passwd)), raising=False)
    monkeypatch.setattr(settings.__class__, "mqtt_password", property(lambda self: "clave-del-backend"), raising=False)
    monkeypatch.setattr(mqtt_auth, "_backend_line", None)
    new_mac = "AA:BB:CC:00:11:22"

    login(client, "oscar")
    assert client.post("/api/devices", json={"mac": new_mac, "name": "X"}, headers=CSRF).status_code == 403

    login(client, "admin")
    assert client.post("/api/devices", json={"mac": "zz", "name": "X"}, headers=CSRF).status_code == 422
    res = client.post("/api/devices", json={"mac": new_mac, "name": "Biodigestor 7", "zone": "Huerta"}, headers=CSRF)
    assert res.status_code == 201, res.text
    body = res.json()
    creds = body["credentials"]
    assert creds["username"] == "aabbcc001122" and len(creds["password"]) == 32
    assert body["node"]["first_connection_pending"] is True and body["node"]["has_credentials"] is True
    assert client.post("/api/devices", json={"mac": new_mac, "name": "Otra"}, headers=CSRF).status_code == 409

    lines = dict(line.split(":", 1) for line in passwd.read_text().splitlines())
    assert mqtt_auth.verify_password("clave-del-backend", lines["backend"])
    assert mqtt_auth.verify_password(creds["password"], lines["aabbcc001122"])

    rotated = client.post("/api/devices/aabbcc001122/credentials", headers=CSRF).json()["credentials"]["password"]
    lines = dict(line.split(":", 1) for line in passwd.read_text().splitlines())
    assert rotated != creds["password"] and mqtt_auth.verify_password(rotated, lines["aabbcc001122"])
    assert not mqtt_auth.verify_password(creds["password"], lines["aabbcc001122"])

    assert client.delete("/api/devices/aabbcc001122/credentials", headers=CSRF).status_code == 204
    assert "aabbcc001122" not in passwd.read_text()
    assert client.get("/api/devices/aabbcc001122").json()["has_credentials"] is False

    client.post("/api/devices/aabbcc001122/credentials", headers=CSRF)
    assert client.delete("/api/devices/aabbcc001122", headers=CSRF).status_code == 204
    assert "aabbcc001122" not in passwd.read_text()


def test_web_app_routes_are_public(client):
    client.cookies.clear()
    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200 and manifest.headers["content-type"].startswith("application/manifest+json")
    body = manifest.json()
    assert body["display"] == "standalone" and any(i["sizes"] == "512x512" for i in body["icons"])
    for icon in body["icons"]:
        assert client.get(icon["src"]).status_code == 200
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and "javascript" in sw.headers["content-type"] and "no-cache" in sw.headers["cache-control"]
    offline = client.get("/offline")
    assert offline.status_code == 200 and "Sin conexión" in offline.text
    for path in ("/static/js/netlink.js", "/static/js/offline.js", "/static/js/connection.js"):
        assert client.get(path).status_code == 200
    health = client.get("/healthz")
    assert health.headers["access-control-allow-origin"] == "*" and health.json()["service"] == "monitor-multinodo"
    assert "worker-src 'self'" in offline.headers["content-security-policy"]


def test_connection_page_and_api(client, fake):
    client.cookies.clear()
    assert client.get("/api/connection").status_code == 401
    assert client.get("/connection", follow_redirects=False).status_code == 303
    make_user("vera", "viewer")
    login(client, "vera")
    info = client.get("/api/connection").json()
    assert info["current"] == "http://testserver" and info["urls"][0] == "http://testserver"
    page = client.get("/connection")
    assert page.status_code == 200 and "Direcciones del servidor" in page.text and 'rel="manifest"' in page.text
