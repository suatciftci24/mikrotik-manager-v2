"""Pure versioned source contracts. Importing this module performs no IO."""
from datetime import datetime,timedelta,timezone
from enum import StrEnum
from hashlib import sha256
from typing import Literal,Protocol
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

class Backend(StrEnum):
    LOCAL='LOCAL'
    RADIUS='RADIUS'

class SourceState(StrEnum):
    AVAILABLE='AVAILABLE'
    NO_DATA='NO_DATA'
    UNKNOWN='UNKNOWN'
    TIMEOUT='TIMEOUT'
    ACCESS_DENIED='ACCESS_DENIED'
    ERROR='ERROR'
    STALE='STALE'
    DISABLED='DISABLED'

class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)

class SecretReference(Contract):
    # Opaque lookup key only. No resolver or secret material is implemented.
    reference:str=Field(pattern=r'^secretref:v2/[a-zA-Z0-9_-]{1,64}/[a-zA-Z0-9_-]{1,64}$')
    purpose:Literal['ROUTEROS_AUTH','RADIUS_AUTH','IPSEC_PSK']

class ExternalConfiguration(Contract):
    routeros_enabled:Literal[False]=False
    radius_enabled:Literal[False]=False
    external_writes:Literal[False]=False
    provider:Literal['SYNTHETIC']='SYNTHETIC'

class Observation(Contract):
    id:str=Field(min_length=1,max_length=160)
    router_id:str=Field(min_length=1,max_length=160)
    source_id:Literal['v2-synthetic']='v2-synthetic'
    kind:Literal['INVENTORY','HEALTH','WAN','IPSEC','PPPOE','SESSION','EVENT']
    revision:int=Field(default=0,ge=0)
    observed_at:datetime|None=None
    status:str|None=Field(default=None,max_length=80)
    backend:Backend|None=None
    subject_id:str|None=Field(default=None,max_length=160)
    # Exact safe summary fields only; no arbitrary provider dictionaries or credentials.
    name:str|None=Field(default=None,max_length=160)
    state:SourceState=SourceState.UNKNOWN
    @field_validator('observed_at')
    @classmethod
    def aware(cls,value):
        if value is not None and value.utcoffset() is None:raise ValueError('Timezone-aware observation required')
        return value

class Batch(Contract):
    version:Literal[1]=1
    source_id:Literal['v2-synthetic']='v2-synthetic'
    router_id:str
    mode:Literal['SNAPSHOT','DELTA']='SNAPSHOT'
    cursor:str=Field(min_length=1,max_length=160)
    base_cursor:str|None=None
    complete:bool=False
    records:tuple[Observation,...]=Field(default=(),max_length=10000)
    @model_validator(mode='after')
    def scope(self):
        if any(row.router_id!=self.router_id or row.source_id!=self.source_id for row in self.records):raise ValueError('Source/router mismatch')
        if self.mode=='DELTA' and not self.base_cursor:raise ValueError('Delta requires base cursor')
        if self.mode=='SNAPSHOT' and self.base_cursor is not None:raise ValueError('Snapshot has no base cursor')
        keys=[(row.kind,row.id) for row in self.records]
        if len(keys)!=len(set(keys)):raise ValueError('Duplicate source record')
        return self

class RouterProvider(Protocol):
    """Only observation reads. No connect, credential or external write operations."""
    def read(self,router_id:str)->Batch:...

# Separate capability names allow later providers without changing consumers.
class InventoryProvider(RouterProvider,Protocol):pass
class PPPoEProvider(RouterProvider,Protocol):pass
class SessionProvider(RouterProvider,Protocol):pass
class WANProvider(RouterProvider,Protocol):pass
class IPsecProvider(RouterProvider,Protocol):pass
class HealthProvider(RouterProvider,Protocol):pass
class EventProvider(RouterProvider,Protocol):pass

class Replica(Contract):
    source_id:Literal['v2-synthetic']='v2-synthetic'
    router_id:str
    cursor:str|None=None
    records:tuple[Observation,...]=()
    # Pure preview state, not a persistent audit/incident ledger.
    receipts:dict[str,str]=Field(default_factory=dict)
    event_receipts:dict[str,str]=Field(default_factory=dict)


def reconcile(state:Replica,batch:Batch)->tuple[Replica,tuple[Observation,...]]:
    """Explicit offline reducer. Never writes audit/incident rows or marks omission DOWN."""
    if (state.source_id,state.router_id)!=(batch.source_id,batch.router_id):raise ValueError('Replica scope mismatch')
    digest=sha256(batch.model_dump_json().encode()).hexdigest()
    if batch.cursor in state.receipts:
        if state.receipts[batch.cursor]!=digest:raise ValueError('Cursor reused with different content')
        return state,()
    if batch.mode=='DELTA' and batch.base_cursor!=state.cursor:raise ValueError('Delta cursor gap')
    previous={(r.kind,r.id):r for r in state.records};changes=[];events=dict(state.event_receipts)
    for row in batch.records:
        old=previous.get((row.kind,row.id))
        if row.kind=='EVENT':
            event_digest=sha256(row.model_dump_json().encode()).hexdigest()
            if row.id in events and events[row.id]!=event_digest:raise ValueError('Event identity reused')
            seen=row.id in events;events[row.id]=event_digest
        else:seen=False
        if old and (row.revision<old.revision or row.revision==old.revision and row!=old):raise ValueError('Stale/conflicting source revision')
        if old!=row and not seen:changes.append(row)
    # Missing rows in incomplete snapshots/deltas retain last observations, never recovery/outage events.
    merged={} if batch.mode=='SNAPSHOT' and batch.complete else dict(previous)
    merged.update({(row.kind,row.id):row for row in batch.records})
    return Replica(router_id=state.router_id,cursor=batch.cursor,records=tuple(merged.values()),receipts={**state.receipts,batch.cursor:digest},event_receipts=events),tuple(changes)


def freshness(row:Observation,now:datetime,max_age:timedelta)->SourceState:
    if now.utcoffset() is None or max_age.total_seconds()<=0:raise ValueError('Explicit clock and positive max age required')
    if row.state not in (SourceState.AVAILABLE,SourceState.STALE):return row.state
    if row.observed_at is None or row.observed_at>now:return SourceState.UNKNOWN
    return SourceState.STALE if now-row.observed_at>max_age else SourceState.AVAILABLE
