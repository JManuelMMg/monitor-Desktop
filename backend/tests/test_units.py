import time

from app import topics
from app.security import (LoginThrottle, create_access_token, decode_access_token, has_role,
                          hash_password, verify_password)
from app.state import Registry, normalize_telemetry


def test_normalize_mac_variants():
    assert topics.normalize_mac("A4:CF:12:B3:C4:D5") == "a4cf12b3c4d5"
    assert topics.normalize_mac("a4-cf-12-b3-c4-d5") == "a4cf12b3c4d5"
    assert topics.normalize_mac("a4cf12b3c4") is None
    assert topics.normalize_mac("zz:cf:12:b3:c4:d5") is None


def test_parse_topics():
    assert topics.parse("monitor/v1/nodes/a4cf12b3c4d5/telemetry") == ("a4cf12b3c4d5", "telemetry")
    assert topics.parse("monitor/v1/nodes/a4cf12b3c4d5/cmd/ack") == ("a4cf12b3c4d5", "cmd/ack")
    assert topics.parse("monitor/v1/nodes/a4cf12b3c4d5/cmd") is None        # saliente
    assert topics.parse("monitor/v1/nodes/A4CF12B3C4D5/telemetry") is None  # mayúsculas
    assert topics.parse("otro/a4cf12b3c4d5/telemetry") is None
    assert topics.node_topic("a4cf12b3c4d5", topics.CONFIG_SET) == "monitor/v1/nodes/a4cf12b3c4d5/config/set"


def test_password_hash_roundtrip():
    encoded = hash_password("una clave larga")
    assert encoded.startswith("scrypt$")
    assert verify_password("una clave larga", encoded)
    assert not verify_password("otra clave", encoded)
    assert not verify_password("x", "basura")


def test_jwt_roundtrip_and_tamper():
    token, _ = create_access_token(7, "operator", 3)
    claims = decode_access_token(token)
    assert claims["sub"] == "7" and claims["ver"] == 3 and claims["role"] == "operator"
    assert decode_access_token(token[:-2] + "aa") is None


def test_roles():
    assert has_role("admin", "operator")
    assert has_role("operator", "operator")
    assert not has_role("viewer", "operator")
    assert not has_role("intruso", "viewer")


def test_login_throttle_locks_and_resets():
    throttle = LoginThrottle(max_failures=3, window_s=60, lockout_s=60)
    for _ in range(3):
        throttle.failure("1.1.1.1", "Ana")
    assert throttle.retry_after("1.1.1.1", "ana") > 0
    assert throttle.retry_after("2.2.2.2", "ana") == 0
    throttle.success("1.1.1.1", "ana")
    assert throttle.retry_after("1.1.1.1", "ana") == 0


def test_normalize_telemetry_rejects_garbage():
    data = normalize_telemetry({"temp_c": 24.5, "hum_pct": 150, "co2_ppm": "800", "ch4_ppm": float("nan"),
                                "dist_cm": True, "mq_ok": 1, "dht_ok": True, "extra": "x"})
    assert data["temp_c"] == 24.5
    assert data["hum_pct"] is None          # fuera de rango
    assert data["co2_ppm"] == 800.0
    assert data["ch4_ppm"] is None          # NaN
    assert data["dist_cm"] is None          # booleano no es número
    assert data["mq_ok"] is False           # solo True estricto
    assert data["dht_ok"] is True
    assert "extra" not in data


def test_registry_connection_and_alarms():
    reg = Registry()
    snap, node, created = reg.on_status("a4cf12b3c4d5", {"state": "online", "fw": "3.0.0"})
    assert created and snap["connection"] == "stale"          # online pero sin telemetría
    snap, _, created = reg.on_telemetry("a4cf12b3c4d5", normalize_telemetry({"temp_c": 50, "ch4_ppm": 100}))
    assert not created and snap["connection"] == "online"
    assert [a["metric"] for a in snap["alarms"]] == ["temp_c"]
    node.telemetry_ts = time.time() - 3600
    assert [c["connection"] for c in reg.connection_changes()] == ["stale"]
    reg.on_status("a4cf12b3c4d5", {"state": "offline"})
    assert reg.snapshot("a4cf12b3c4d5")["connection"] == "offline"


def test_mosquitto_hash_format():
    from app import mqtt_auth
    encoded = mqtt_auth.hash_password("secreto")
    _, kind, iterations, salt, digest = encoded.split("$")
    assert kind == "7" and int(iterations) == mqtt_auth.ITERATIONS
    assert len(salt) == 16 and len(digest) == 88            # 12 y 64 bytes en base64
    assert mqtt_auth.verify_password("secreto", encoded)
    assert not mqtt_auth.verify_password("otro", encoded)
    # Recalcula el PBKDF2-SHA512 tal como lo verifica Mosquitto al autenticar.
    import base64
    import hashlib
    salt_b = base64.b64decode(salt)
    assert base64.b64encode(hashlib.pbkdf2_hmac("sha512", b"secreto", salt_b, int(iterations))).decode() == digest
