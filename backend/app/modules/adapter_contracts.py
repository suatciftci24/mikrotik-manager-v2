"""Protocol boundaries only. Phase 1 has no implementation that opens a connection."""
from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from app.simulation.aaa_integration_preparation import SyntheticAaaCommand, SyntheticAaaReceipt


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
    async def apply_subscriber(self, command: 'SyntheticAaaCommand') -> 'SyntheticAaaReceipt':
        """CREATE/EXTEND/PLAN/STATUS: actor, tenant, router, source, CAS, UUID and audit.

        V1 is fixture-only. A live implementation MUST reject this version;
        production dispatch requires a separately accepted contract/version.
        UNKNOWN must never be retried as a new write.
        """
        ...
    async def create_local_subscriber(self, account: LocalSubscriberCredential) -> dict: ...


class FreeRadiusAdapter(Protocol):
    """Future FreeRADIUS SQL/API contract. Production credentials are forbidden in Phase 1."""
    async def health(self) -> dict: ...
    async def apply_subscriber(self, command: 'SyntheticAaaCommand') -> 'SyntheticAaaReceipt':
        """Same idempotency/CAS/receipt contract; V1 fixture input is not live authority.

        No direct SQL fallback or success on response loss. Accepting production
        commands needs an independently approved provider contract/version.
        """
        ...
    async def create_identity(self, identity: RadiusIdentity) -> dict: ...
    async def disable_identity(self, identity: RadiusIdentity) -> dict: ...
