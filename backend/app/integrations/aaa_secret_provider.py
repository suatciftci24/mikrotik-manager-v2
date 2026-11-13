"""Replaceable verification boundary. No secret export, transport or app wiring."""
from datetime import datetime
from hmac import compare_digest
from typing import Protocol, Literal
from uuid import UUID
from pydantic import Field, SecretStr
from app.integrations.aaa_contracts import ReadContract


class SecretVerificationScope(ReadContract):
    tenant_id: UUID
    actor_id: str
    subscriber_id: str
    router_id: str
    source: Literal['LOCAL','RADIUS']
    purpose: Literal['SUBSCRIBER_PASSWORD','ROUTER_LOGIN','RADIUS_SHARED_SECRET']
    revision: int = Field(ge=1)


class SecretVerificationProvider(Protocol):
    """Implementations MUST enforce scope/deadline and never log or export values.

    A failure is denial; implementations must bound IO themselves. No automatic
    retries. No production implementation is provided or selected by default.
    """
    def verify_password(self, reference: str, scope: SecretVerificationScope,
                        candidate: SecretStr, *, now: datetime, deadline: datetime) -> bool: ...


class SyntheticPasswordEntry(ReadContract):
    reference: str = Field(repr=False, exclude=True)
    scope: SecretVerificationScope
    password: SecretStr = Field(repr=False, exclude=True)
    active: bool = True


class SyntheticSecretProvider:
    """Explicit caller-owned synthetic values only; no store IO or value getter."""
    def __init__(self, entries):
        self._entries = tuple(entries)
        if any(type(e) is not SyntheticPasswordEntry for e in self._entries):
            raise TypeError('SYNTHETIC_PASSWORD_ENTRIES_REQUIRED')

    def verify_password(self, reference, scope, candidate, *, now, deadline):
        if (type(candidate) is not SecretStr or type(scope) is not SecretVerificationScope
                or now.utcoffset() is None or deadline.utcoffset() is None or now >= deadline):
            return False
        matches = [e for e in self._entries if e.reference == reference and e.scope == scope and e.active is True]
        return len(matches) == 1 and compare_digest(
            matches[0].password.get_secret_value().encode(), candidate.get_secret_value().encode())


class RadiusFixturePasswordVerifier:
    """PAP/CLEARTEXT_REFERENCE only. Fresh trusted authorization on both sides.

    The callback is injected by trusted caller, never supplied by an API body.
    This is a synthetic FreeRADIUS3 auth flow, not a RADIUS protocol server.
    """
    def __init__(self, provider: SecretVerificationProvider, gate, authorize, clock):
        if not callable(getattr(provider,'verify_password',None)) or not callable(authorize) or not callable(clock):
            raise TypeError('EXPLICIT_PASSWORD_VERIFICATION_DEPENDENCIES_REQUIRED')
        self.provider, self.gate, self.authorize, self.clock = provider, gate, authorize, clock

    def verify(self, adapter, command, candidate):
        # Fixed result: no exception details, reference or secret in public output.
        try:
            from app.adapters.aaa_freeradius import FreeRadiusFixtureAdapter
            from app.modules.adapter_contracts import bound_adapter_command
            if type(adapter) is not FreeRadiusFixtureAdapter or type(candidate) is not SecretStr:
                return False
            command,target,_ = bound_adapter_command(command,adapter.target,'RADIUS')
            now = self.clock()
            projection = adapter.prepare(command,now)
            if (target.password.method != 'PAP' or target.password.storage != 'CLEARTEXT_REFERENCE'
                    or projection.authorization.control.get('Auth-Type') == 'Reject'):
                return False
            scope = SecretVerificationScope(tenant_id=command.tenant_id,actor_id=command.actor_id,
                subscriber_id=command.subscriber_id,router_id=command.router_id,source='RADIUS',
                purpose='SUBSCRIBER_PASSWORD',revision=self.gate.revision)
            if self.authorize(scope) is not True:
                return False
            self.gate.check(command,target,now)
            result = self.provider.verify_password(target.password.credential_reference,scope,candidate,
                now=now,deadline=self.gate.valid_until)
            # Recheck revocation and deadline after even a slow/replaced provider.
            if self.authorize(scope) is not True:
                return False
            finished = self.clock()
            self.gate.check(command,target,finished)
            if adapter.prepare(command,finished).authorization.control.get('Auth-Type') == 'Reject':
                return False
            return result is True
        except Exception:
            return False
