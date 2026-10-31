"""Explicit per-router read bindings; startup and environment never enable IO."""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Literal
from threading import RLock
from pydantic import BaseModel, ConfigDict, Field
from app.adapters.pppoe_readonly import PppoeReadAdapter, PppoeObservation, RouterReadSettings


class TimedPppoeObservation(PppoeObservation):
    source_status: Literal['FRESH', 'STALE', 'UNKNOWN']


class PppoeSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    router_id: str
    availability: Literal['AVAILABLE', 'UNAVAILABLE']
    items: list[TimedPppoeObservation] = Field(default_factory=list)
    error: Literal['DISABLED', 'DEMO_ISOLATED', 'INVALID_DATA', 'TIMEOUT', 'CONNECTION_FAILED', 'AUTHORITY_MISMATCH'] | None = None
    selected_source: Literal['LOCAL', 'RADIUS'] | None = None
    last_successful_observed_at: datetime | None = None
    is_demo: bool = False
    read_only: Literal[True] = True


@dataclass(frozen=True)
class PppoeReadBinding:
    router_id: str
    adapter: PppoeReadAdapter = field(repr=False)
    settings: RouterReadSettings = field(repr=False)
    # Authoritative inventory IDs scoped to this router; never infer from username.
    authorities: dict[str, Literal['LOCAL', 'RADIUS']] = field(repr=False)
    last_measurements: dict = field(default_factory=dict, repr=False, compare=False)
    lock: object = field(default_factory=RLock, repr=False, compare=False)


def disabled_binding() -> PppoeReadBinding | None:
    """FastAPI dependency: no transport, credentials, environment or socket access."""
    return None


def snapshot(router_id: str, *, is_demo: bool, binding: PppoeReadBinding | None, source: Literal['LOCAL', 'RADIUS'] | None = None, account_id: str | None = None) -> PppoeSnapshot:
    def unavailable(error):
        return PppoeSnapshot(router_id=router_id, availability='UNAVAILABLE', error=error, is_demo=is_demo, selected_source=source)
    if is_demo:
        return unavailable('DEMO_ISOLATED')
    if binding is None or binding.router_id != router_id:
        return unavailable('DISABLED')
    # Copy the inventory before IO so authority cannot change during the read.
    authorities = dict(binding.authorities)
    if not authorities or any(source not in ('LOCAL', 'RADIUS') for source in authorities.values()):
        return unavailable('AUTHORITY_MISMATCH')
    if source not in (None, 'LOCAL', 'RADIUS') or (account_id is not None and (account_id not in authorities or source != authorities[account_id])):
        return unavailable('AUTHORITY_MISMATCH')
    key = (source, account_id)
    with binding.lock:
        return _read_snapshot(router_id, binding, authorities, source, account_id, key)


def _read_snapshot(router_id, binding, authorities, source, account_id, key):
    def unavailable(error):
        return PppoeSnapshot(router_id=router_id, availability='UNAVAILABLE', error=error,
            selected_source=source, last_successful_observed_at=binding.last_measurements.get(key))
    result = binding.adapter.read(binding.settings)
    if result.availability != 'AVAILABLE':
        return unavailable(result.error)
    if any(authorities.get(item.account_id) != item.source for item in result.items):
        return unavailable('AUTHORITY_MISMATCH')
    now = datetime.now(timezone.utc)
    items = [TimedPppoeObservation(**item.model_dump(), source_status=(
        'UNKNOWN' if item.observed_at is None else
        'STALE' if now - item.observed_at > timedelta(minutes=5) else 'FRESH')) for item in result.items if (source is None or item.source == source) and (account_id is None or item.account_id == account_id)]
    stamps = [item.observed_at for item in items if item.observed_at is not None]
    if stamps:
        latest = max(stamps)
        previous = binding.last_measurements.get(key)
        binding.last_measurements[key] = max(previous, latest) if previous else latest
    return PppoeSnapshot(router_id=router_id, availability='AVAILABLE', items=items, selected_source=source,
        last_successful_observed_at=binding.last_measurements.get(key))


def api_ssl_binding(router_id, settings, accounts, policy=None):
    """Build an offline opt-in binding; callers still require central authorization.

    Does not read environment, open sockets or register a dependency. The
    transport defaults to a disabled connection policy even with credentials.
    """
    from app.adapters.pppoe_api_ssl import RouterPppoeApiSslTransport
    from app.adapters.router_api_ssl import ConnectionPolicy
    accounts = tuple(accounts)
    transport = RouterPppoeApiSslTransport(settings, accounts, policy or ConnectionPolicy())
    return PppoeReadBinding(router_id, PppoeReadAdapter(transport), settings,
                           {account.account_id: account.source for account in accounts})
