from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from app.schemas.subscriber_events import ExpiryChange
from app.schemas.package import PackageFields

class SyntheticSubscriberFields(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    customer_name:str=Field(min_length=2,max_length=160)
    username:str=Field(min_length=1,max_length=96,pattern=r'^[A-Za-z0-9][A-Za-z0-9._@-]*$')
    router_id:str=Field(pattern=r'^demo-managed-router-[0-9a-f-]{36}$')
    access_type:Literal['PPPOE','HOTSPOT']
    source:Literal['LOCAL','RADIUS']
    package_id:str|None=Field(default=None,pattern=r'^demo-package-[0-9a-f-]{36}$')
    package_revision:int|None=Field(default=None,ge=1)
    plan:str=Field(min_length=1,max_length=120)
    status:Literal['ACTIVE','PAUSED']='PAUSED'
    started_on:date|None=None
    expires_on:date|None=None
    @field_validator('customer_name','plan')
    @classmethod
    def printable(cls,value):
        if not value.isprintable():raise ValueError('Yazdırılabilir metin gerekli.')
        return value
    @model_validator(mode='after')
    def ordered_dates(self):
        if bool(self.package_id)!=(self.package_revision is not None):raise ValueError('Paket kimliği ve revizyonu birlikte gerekli.')
        if self.started_on and self.expires_on and self.expires_on<self.started_on:raise ValueError('Bitiş tarihi başlangıç tarihinden önce olamaz.')
        return self
    _date=field_validator('started_on','expires_on',mode='before')(ExpiryChange.calendar_date_only.__func__)

class SyntheticSubscriberCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:UUID
    fields:SyntheticSubscriberFields
    expected_revision:int=Field(default=0,ge=0)
    confirmed:Literal[True]
    @field_validator('confirmed',mode='before')
    @classmethod
    def explicit(cls,value):
        if value is not True:raise ValueError('Açık onay gerekli.')
        return value

class CenterSubscriber(BaseModel):
    can_manage:bool=False
    id:str
    customer_name:str
    username:str
    router_id:str|None=None
    router_name:str|None=None
    router_model:str|None=None
    router_missing:bool=False
    router_source:Literal['PERSISTENT_DEMO','STATIC_DEMO','UNKNOWN']='UNKNOWN'
    access_type:Literal['PPPOE','HOTSPOT']|None=None
    source:Literal['LOCAL','RADIUS']|None=None
    package_id:str|None=None
    package_revision:int|None=None
    package_snapshot:PackageFields|None=None
    plan:str
    status:str
    started_on:date|None=None
    expires_on:date|None=None
    revision:int
    ip_address:str|None=None
    last_seen_at:str|None=None
    last_connected_at:str|None=None
    session_status:Literal['UNKNOWN']='UNKNOWN'

class CenterSubscriberEvent(BaseModel):
    request_id:str|None=None
    source:Literal['LOCAL','RADIUS']|None=None
    operation:str
    occurred_at:str
    actor_id:str
    revision:int|None=None
    previous_expires_on:date|None=None
    started_on:date|None=None
    expires_on:date|None=None
    date_changed:bool=False
    result:Literal['APPLIED','FAILED']='APPLIED'
    error:str|None=None
    subscriber_id:str|None=None
    router_id:str|None=None
    previous_values:dict[str,str|None]=Field(default_factory=dict)
    new_values:dict[str,str|None]=Field(default_factory=dict)

class SubscriberCenterData(BaseModel):
    item:CenterSubscriber
    is_demo:Literal[True]=True
    source:Literal['PERSISTENT_WORKSPACE','LEGACY_DEMO']
    persistence:Literal['local-postgresql-workspace','local-postgresql-demo','process-memory']
    device_connection_started:Literal[False]=False
    history:list[CenterSubscriberEvent]=Field(default_factory=list)
    connection_history:list[dict]=Field(default_factory=list)

class SubscriberWorkspaceList(BaseModel):
    items:list[CenterSubscriber]
    total:int
    page:int
    page_size:int
    is_demo:Literal[True]=True

class SubscriberRenewal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:UUID
    expected_revision:int=Field(ge=1)
    expected_source:Literal['LOCAL','RADIUS']
    expected_expires_on:date|None
    expires_on:date
    days:Literal[7,15,30,60,90]|None=None
    confirmed:Literal[True]
    _confirmed=field_validator('confirmed',mode='before')(SyntheticSubscriberCommand.explicit.__func__)
    _dates=field_validator('expected_expires_on','expires_on',mode='before')(ExpiryChange.calendar_date_only.__func__)

class RouterSubscriberList(SubscriberWorkspaceList):
    is_demo:bool
    total:int|None
    source:Literal['PERSISTENT_WORKSPACE','LEGACY_DEMO','REGISTERED']
    availability:Literal['AVAILABLE','PREPARING']='AVAILABLE'


class SubscriberRequestAudit(BaseModel):
    request_id:UUID
    item_id:str
    actor_id:str
    router_id:str
    source:Literal['LOCAL','RADIUS']
    revision:int=Field(ge=1)
    operation:str
    occurred_at:str
    success:bool
    storage:Literal['PERSISTENT_WORKSPACE']='PERSISTENT_WORKSPACE'
    is_demo:Literal[True]=True

class SubscriberSaveResult(BaseModel):
    request_id:UUID
    status:Literal['SUCCESS','UNKNOWN']
    response:CenterSubscriber|None=None
    audit:SubscriberRequestAudit|None=None
