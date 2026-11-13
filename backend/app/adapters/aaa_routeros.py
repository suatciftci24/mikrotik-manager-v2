"""RouterOS 6/7 PPP secret API projections; no transport, shell or REST client."""
from datetime import datetime
from typing import Literal
from app.integrations.aaa_identity_writer_boundary import AaaBoundaryDisabled
from app.modules.adapter_contracts import (AaaAdapterProjection,AaaAdapterTarget,
    bound_adapter_command,adapter_envelope)


class RouterOsProjection(AaaAdapterProjection):
    routeros_major: Literal[6,7]
    api_path: Literal['/ppp/secret/add','/ppp/secret/set'] | None
    action: Literal['ADD','SET','METADATA_ONLY']
    values: dict[str,str]
    credential_action: Literal['SET_FROM_REFERENCE','PRESERVE']
    expiration_enforcement: Literal['EXTERNAL_WORKER_REQUIRED','UNSPECIFIED']
    disconnect_existing_sessions: Literal[False] = False


class RouterOsFixtureAdapter:
    def __init__(self, target: AaaAdapterTarget):
        self.target = target

    def prepare(self, command, now: datetime):
        command, target, profile = bound_adapter_command(command,self.target,'LOCAL')
        if now.utcoffset() is None:
            raise PermissionError('AWARE_ADAPTER_TIME_REQUIRED')
        envelope = adapter_envelope(command,target)
        expiry = envelope['expires_at_utc']
        disabled = 'yes' if command.after.status=='PAUSED' or expiry is not None and expiry<=now else 'no'
        values = {}
        if command.operation=='CREATE':
            if target.routeros_record_id is not None:
                raise PermissionError('ROUTEROS_ACCOUNT_ALREADY_BOUND')
            if target.password is None or target.password.storage!='CLEARTEXT_REFERENCE':
                raise PermissionError('ROUTEROS_CREATE_CREDENTIAL_REFERENCE_REQUIRED')
            action, path = 'ADD','/ppp/secret/add'
            values = {'name':command.after.username,'service':'pppoe','profile':profile.profile,'disabled':disabled}
        elif command.operation=='EXTEND':
            # PPP secret has no native absolute expiry; never invent an API key
            # or mistake session-timeout for an account lifetime.
            action, path = 'METADATA_ONLY',None
        else:
            if target.routeros_record_id is None:
                raise PermissionError('VERIFIED_ROUTEROS_RECORD_ID_REQUIRED')
            action, path = 'SET','/ppp/secret/set'
            values = {'.id':target.routeros_record_id}
            if command.operation=='PLAN': values['profile']=profile.profile
            else: values['disabled']=disabled
        return RouterOsProjection(**envelope,routeros_major=target.routeros_major,api_path=path,action=action,
            values=values,credential_action='SET_FROM_REFERENCE' if command.operation=='CREATE' else 'PRESERVE',
            expiration_enforcement='EXTERNAL_WORKER_REQUIRED' if expiry is not None else 'UNSPECIFIED')

    async def apply_subscriber(self, command):
        raise AaaBoundaryDisabled('AAA_REAL_ROUTEROS_WRITER_NOT_ENABLED')
