"""Offline-ready PPPoE read boundary. Never registered by demo/startup code.

A future approved transport must enforce TLS, deadline and row bounds before
returning. No generic command or mutation method is exposed to domain callers.
"""
from dataclasses import dataclass, field
from ipaddress import IPv4Address
import os
from typing import Literal, Protocol
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError


class ReadConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class RouterReadSettings:
    address: str
    username: str = field(repr=False)
    password: SecretStr = field(repr=False)
    ca_pem: str = field(repr=False)
    leaf_sha256: str
    port: int = 8729
    timeout_seconds: float = 2

    @classmethod
    def environment(cls):
        """Parse only dedicated V2 variables; no files, DNS or sockets are read."""
        import re
        try:
            address = str(IPv4Address(os.environ['V2_ROUTER_READ_ADDRESS']))
            username = os.environ['V2_ROUTER_READ_USERNAME']
            password = os.environ['V2_ROUTER_READ_PASSWORD']
            ca = os.environ['V2_ROUTER_READ_CA_PEM']
            pin = os.environ['V2_ROUTER_READ_LEAF_SHA256']
            port = int(os.environ.get('V2_ROUTER_READ_PORT', '8729'))
            timeout = float(os.environ.get('V2_ROUTER_READ_TIMEOUT_SECONDS', '2'))
            if not username.strip() or not password or not ca.strip():
                raise ValueError()
            if any(c in username + password for c in '\r\n\x00'):
                raise ValueError()
            if port != 8729 or not 0.1 <= timeout <= 10 or not re.fullmatch('[a-f0-9]{64}', pin):
                raise ValueError()
            return cls(address, username, SecretStr(password), ca, pin, port, timeout)
        except (KeyError, ValueError, TypeError):
            raise ReadConfigurationError('ROUTER_READ_CONFIG_INVALID') from None


class PppoeObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, hide_input_in_errors=True)
    account_id: str = Field(min_length=1, max_length=80)
    # Authority comes from the account inventory, never inferred from a session.
    source: Literal['LOCAL', 'RADIUS']
    connected: bool | None = None
    ip_address: str | None = None


class PppoeReadTransport(Protocol):
    def read_pppoe(self, settings: RouterReadSettings) -> list[dict]: ...


@dataclass(frozen=True)
class PppoeReadResult:
    availability: Literal['AVAILABLE', 'UNAVAILABLE']
    items: tuple[PppoeObservation, ...] = ()
    error: str | None = None
    is_demo: Literal[False] = False
    read_only: Literal[True] = True


class PppoeReadAdapter:
    def __init__(self, transport: PppoeReadTransport):
        self.transport = transport

    def read(self, settings: RouterReadSettings) -> PppoeReadResult:
        try:
            rows = self.transport.read_pppoe(settings)
            if not isinstance(rows, list) or len(rows) > 128:
                return PppoeReadResult('UNAVAILABLE', error='INVALID_DATA')
            items = tuple(PppoeObservation.model_validate(row) for row in rows)
            if len({item.account_id for item in items}) != len(items):
                return PppoeReadResult('UNAVAILABLE', error='INVALID_DATA')
            # Reject credential echoes even in otherwise valid public fields.
            password = settings.password.get_secret_value()
            if any(password in str(item.model_dump()) for item in items):
                return PppoeReadResult('UNAVAILABLE', error='INVALID_DATA')
            return PppoeReadResult('AVAILABLE', items)
        except TimeoutError:
            return PppoeReadResult('UNAVAILABLE', error='TIMEOUT')
        except (ValidationError, ValueError, TypeError):
            return PppoeReadResult('UNAVAILABLE', error='INVALID_DATA')
        except Exception:
            return PppoeReadResult('UNAVAILABLE', error='CONNECTION_FAILED')
