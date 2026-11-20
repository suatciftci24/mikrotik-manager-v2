"""Sanitized RouterOS observations. No transport credentials or raw comments."""
from ipaddress import IPv4Address, IPv6Address
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from datetime import date
import re
from typing import Annotated

Text = Annotated[str, Field(min_length=1, max_length=120)]

class Projection(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)

    @field_validator('*')
    @classmethod
    def public_text(cls, value):
        if isinstance(value, str) and (not value.isprintable() or re.search(
            r'password=|passwd=|secretref:|token=|psk=|private[ _-]?key|-----begin', value, re.I
        )):
            raise ValueError('Unsafe public data')
        return value

class Session(Projection):
    address: IPv4Address | IPv6Address | None = None
    uptime: Text | None = None

class UnmatchedSession(Session):
    username: Text

class Account(Projection):
    username: Text
    profile: Text | None = None
    enabled: bool | None = None
    expires_on: date | None = None
    sessions: list[Session] | None = Field(default=None, max_length=128)

class RouterObservation(Projection):
    id: str = Field(pattern=r'^device-[a-zA-Z0-9_-]{1,80}$')
    identity: Text | None = None
    model: Text | None = None
    routeros_version: str | None = Field(default=None, max_length=64, pattern=r'^[67]\.\d')
    observed_at: AwareDatetime
    last_success_at: AwareDatetime | None = None
    connection: Literal['ONLINE', 'OFFLINE', 'UNKNOWN']
    error: Literal['TIMEOUT', 'UNREACHABLE', 'AUTHORIZATION', 'TLS', 'INVALID_DATA'] | None = None
    cpu_percent: int | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    uptime: Text | None = None
    wan_interface: Text | None = None
    wan_status: Literal['UP', 'DOWN', 'UNKNOWN'] = 'UNKNOWN'
    rx_bytes: int | None = Field(default=None, ge=0, le=2**64-1)
    tx_bytes: int | None = Field(default=None, ge=0, le=2**64-1)
    accounts: list[Account] | None = Field(default=None, max_length=128)
    accounts_complete: bool = False
    unmatched_sessions: list[UnmatchedSession] | None = Field(default=None, max_length=128)

class DeviceInventory(Projection):
    source: Literal['ROUTEROS_READ_ONLY']
    routers: list[RouterObservation] = Field(max_length=64)
