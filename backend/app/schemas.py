from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["viewer", "operator", "admin"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(Strict):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class PasswordChangeIn(Strict):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class UserCreate(Strict):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=128)
    role: Role = "viewer"


class UserPatch(Strict):
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, max_length=128)


class Thresholds(Strict):
    temp_c_max: float | None = Field(default=None, ge=-40, le=85)
    ch4_ppm_max: float | None = Field(default=None, ge=0, le=50000)
    co2_ppm_max: float | None = Field(default=None, ge=0, le=10000)
    level_pct_max: float | None = Field(default=None, ge=0, le=100)


class DeviceCreate(Strict):
    mac: str = Field(min_length=12, max_length=17, description="AA:BB:CC:DD:EE:FF o aabbccddeeff")
    name: str = Field(min_length=1, max_length=80)
    zone: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class DevicePatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    zone: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None
    thresholds: Thresholds | None = None


class NodeConfigIn(Strict):
    """Mismos límites que valida el firmware (applyRemoteConfig)."""
    interval_ms: int = Field(ge=2000, le=600000)
    dht_temp_offset: float = Field(ge=-10, le=10)
    dht_hum_offset: float = Field(ge=-30, le=30)
    us_offset_cm: float = Field(ge=-100, le=100)
    us_scale: float = Field(ge=0.5, le=2.0)
    reactor_empty_cm: float = Field(ge=2, le=450)
    reactor_full_cm: float = Field(ge=0, le=450)
    co2_abc: bool
    status_led: bool

    @model_validator(mode="after")
    def check_reactor(self):
        if self.reactor_full_cm >= self.reactor_empty_cm:
            raise ValueError("reactor_full_cm debe ser menor que reactor_empty_cm")
        return self


Command = Literal["ping", "reboot", "identify", "calibrate_mq4", "clear_mq4", "calibrate_co2_zero"]


class CommandIn(Strict):
    cmd: Command
    seconds: int | None = Field(default=None, ge=1, le=120, description="Solo para identify")
