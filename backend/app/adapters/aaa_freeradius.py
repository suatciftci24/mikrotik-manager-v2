"""FreeRADIUS 3 attribute projections only. No SQL, sockets or password resolver."""
from datetime import datetime
from typing import Literal
from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.integrations.aaa_identity_writer_boundary import AaaBoundaryDisabled
from app.modules.adapter_contracts import (AaaAdapterProjection, AaaAdapterTarget,
    bound_adapter_command, adapter_envelope)


class RadiusAuthentication(ReadContract):
    method: Literal['PAP','CHAP','MSCHAPV2']
    password_attribute: Literal['Cleartext-Password','NT-Password','Crypt-Password']
    action: Literal['SET_FROM_REFERENCE','PRESERVE']
    credential_reference: str | None = Field(default=None,repr=False,exclude=True)


class RadiusAuthorization(ReadContract):
    # Full desired image of managed attributes, not raw SQL or user supplied AVPs.
    control: dict[str, str | int]
    reply: dict[str, str | int]
    managed_control: tuple[str,...] = ('Expiration','Auth-Type')
    managed_reply: tuple[str,...] = ('Mikrotik-Group','Mikrotik-Rate-Limit','Session-Timeout')
    nas_identifier: str
    require_nas_scope: Literal[True] = True
    expiration_module_required: Literal[True] = True
    expiration_policy: Literal['END_OF_DAY_INCLUSIVE','UNSPECIFIED']


class RadiusProjection(AaaAdapterProjection):
    freeradius_major: Literal[3] = 3
    username: str
    authentication: RadiusAuthentication
    authorization: RadiusAuthorization


class FreeRadiusFixtureAdapter:
    """An explicit caller-owned target, never a live dispatcher or authorization grant."""
    def __init__(self, target: AaaAdapterTarget):
        self.target = target

    def prepare(self, command, now: datetime):
        command, target, profile = bound_adapter_command(command,self.target,'RADIUS')
        if now.utcoffset() is None or target.password is None:
            raise PermissionError('AWARE_TIME_AND_PASSWORD_MODEL_REQUIRED')
        attrs = {'CLEARTEXT_REFERENCE':'Cleartext-Password','NT_HASH_REFERENCE':'NT-Password','CRYPT_REFERENCE':'Crypt-Password'}
        password = target.password
        auth = RadiusAuthentication(method=password.method,password_attribute=attrs[password.storage],
            action='SET_FROM_REFERENCE' if command.operation=='CREATE' else 'PRESERVE',
            credential_reference=password.credential_reference if command.operation=='CREATE' else None)
        envelope = adapter_envelope(command,target)
        expiry = envelope['expires_at_utc']
        control, reply = {}, {'Mikrotik-Group':profile.profile}
        if profile.rate_limit is not None:
            reply['Mikrotik-Rate-Limit'] = profile.rate_limit
        if expiry is not None:
            epoch = int(expiry.timestamp())
            if not 0 <= epoch <= 0xffffffff:
                raise ValueError('RADIUS_DATE_OUT_OF_RANGE')
            # A typed date AVP in UTC; transport-specific SQL string encoding is absent.
            control['Expiration'] = epoch
            remaining = int((expiry-now).total_seconds())
            if remaining > 0:
                reply['Session-Timeout'] = remaining
        if command.after.status=='PAUSED' or expiry is not None and expiry<=now:
            control['Auth-Type'] = 'Reject'
        return RadiusProjection(**envelope,username=command.after.username,authentication=auth,
            authorization=RadiusAuthorization(control=control,reply=reply,nas_identifier=target.nas_identifier,
                managed_control=('Expiration','Auth-Type') if expiry is not None else ('Auth-Type',),
                expiration_policy='END_OF_DAY_INCLUSIVE' if expiry is not None else 'UNSPECIFIED'))

    async def apply_subscriber(self, command):
        raise AaaBoundaryDisabled('AAA_REAL_FREERADIUS_WRITER_NOT_ENABLED')
