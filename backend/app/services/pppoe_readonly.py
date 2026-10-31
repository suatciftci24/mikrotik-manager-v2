"""Explicit per-router read bindings; startup and environment never enable IO."""
from dataclasses import dataclass, field
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.adapters.pppoe_readonly import PppoeReadAdapter, PppoeObservation, RouterReadSettings


class PppoeSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    router_id: str
    availability: Literal['AVAILABLE', 'UNAVAILABLE']
    items: list[PppoeObservation] = Field(default_factory=list)
    error: Literal['DISABLED', 'DEMO_ISOLATED', 'INVALID_DATA', 'TIMEOUT', 'CONNECTION_FAILED', 'AUTHORITY_MISMATCH'] | None = None
    is_demo: bool = False
    read_only: Literal[True] = True


@dataclass(frozen=True)
class PppoeReadBinding:
    router_id: str
    adapter: PppoeReadAdapter = field(repr=False)
    settings: RouterReadSettings = field(repr=False)
    # Authoritative inventory IDs scoped to this router; never infer from username.
    authorities: dict[str, Literal['LOCAL', 'RADIUS']] = field(repr=False)


def disabled_binding() -> PppoeReadBinding | None:
    """FastAPI dependency: no transport, credentials, environment or socket access."""
    return None


def snapshot(router_id: str, *, is_demo: bool, binding: PppoeReadBinding | None) -> PppoeSnapshot:
    def unavailable(error):
        return PppoeSnapshot(router_id=router_id, availability='UNAVAILABLE', error=error, is_demo=is_demo)
    if is_demo:
        return unavailable('DEMO_ISOLATED')
    if binding is None or binding.router_id != router_id:
        return unavailable('DISABLED')
    # Copy the inventory before IO so authority cannot change during the read.
    authorities = dict(binding.authorities)
    if not authorities or any(source not in ('LOCAL', 'RADIUS') for source in authorities.values()):
        return unavailable('AUTHORITY_MISMATCH')
    result = binding.adapter.read(binding.settings)
    if result.availability != 'AVAILABLE':
        return unavailable(result.error)
    if any(authorities.get(item.account_id) != item.source for item in result.items):
        return unavailable('AUTHORITY_MISMATCH')
    return PppoeSnapshot(router_id=router_id, availability='AVAILABLE', items=list(result.items))
