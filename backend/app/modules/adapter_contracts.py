"""Protocol boundaries only. Phase 1 has no implementation that opens a connection."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LocalSubscriberCredential:
    router_id: str
    username: str
    secret_reference: str  # Reference to an external V2 secret store; never the password.


@dataclass(frozen=True)
class RadiusIdentity:
    username: str
    realm: str
    nas_identifier: str


class RouterOSAdapter(Protocol):
    """Future RouterOS API contract. Implementations must be injected explicitly."""
    async def health(self, router_id: str) -> dict: ...
    async def list_pppoe_sessions(self, router_id: str) -> list[dict]: ...
    async def create_local_subscriber(self, account: LocalSubscriberCredential) -> dict: ...


class FreeRadiusAdapter(Protocol):
    """Future FreeRADIUS SQL/API contract. Production credentials are forbidden in Phase 1."""
    async def health(self) -> dict: ...
    async def create_identity(self, identity: RadiusIdentity) -> dict: ...
    async def disable_identity(self, identity: RadiusIdentity) -> dict: ...
