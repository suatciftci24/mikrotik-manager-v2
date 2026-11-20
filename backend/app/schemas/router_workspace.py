from datetime import datetime, timezone
from ipaddress import IPv4Address,IPv4Network
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator

class DemoRouterFields(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=120)
    management_address:IPv4Address
    model:str=Field(default='Sentetik model',min_length=1,max_length=120)
    site:str=Field(default='',max_length=120)
    identity:str=Field(default='',max_length=120)
    routeros_version:str=Field(default='',max_length=60)
    description:str=Field(default='',max_length=500)
    management_status:Literal['ACTIVE','INACTIVE']='ACTIVE'
    simulated_status:Literal['ONLINE','OFFLINE','UNKNOWN']='UNKNOWN'
    simulated_last_seen_at:datetime|None=None

    @field_validator('simulated_last_seen_at')
    @classmethod
    def normalize_simulated_time(cls,value):
        if value is None:
            return None
        if value.tzinfo is None or value > datetime.now(timezone.utc):
            raise ValueError('Sentetik son görülme geçmiş veya güncel bir saat dilimli zaman olmalı.')
        return value.astimezone(timezone.utc)

    @field_validator('management_address')
    @classmethod
    def documentation_only(cls,value):
        if not any(value in IPv4Network(cidr) for cidr in ('192.0.2.0/24','198.51.100.0/24','203.0.113.0/24')):
            raise ValueError('Yalnız sentetik dokümantasyon IPv4 adresleri kullanılabilir.')
        return value
    @field_validator('name','model','site','identity','routeros_version')
    @classmethod
    def clean_text(cls,value):
        if any(ord(c)<32 for c in value):raise ValueError('Kontrol karakteri kabul edilmez.')
        return value

    @field_validator('description')
    @classmethod
    def clean_description(cls,value):
        value=value.replace('\r\n','\n').replace('\r','\n')
        cls.clean_text(value.replace('\n',' '))
        return value


class TrustProfileFields(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=120)
    management_address:IPv4Address
    port:int=Field(default=8729,ge=1024,le=65535)
    ca_pem:str=Field(min_length=1,max_length=262144)
    leaf_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    @field_validator('port')
    @classmethod
    def ssl_only(cls,value):
        if value==8728:raise ValueError('Düz API kabul edilmez.')
        return value

class DemoRouterCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:UUID
    fields:DemoRouterFields
    expected_revision:int=Field(default=0,ge=0)
    confirmed:Literal[True]
    @field_validator('confirmed',mode='before')
    @classmethod
    def explicit(cls,value):
        if value is not True:raise ValueError('Açık onay gerekli.')
        return value

class TrustProfileCommand(DemoRouterCommand):
    fields:TrustProfileFields

class DeleteWorkspaceRecord(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=1)
    confirmed:Literal[True]
    _explicit=field_validator('confirmed',mode='before')(DemoRouterCommand.explicit.__func__)

class WorkspaceRecord(BaseModel):
    id:str
    kind:Literal['DEMO_ROUTER','TRUST_PROFILE']
    revision:int
    fields:DemoRouterFields|TrustProfileFields
    is_demo:bool
    device_connected:Literal[False]=False
    persistence:Literal['local-postgresql-workspace']='local-postgresql-workspace'

class WorkspaceList(BaseModel):
    items:list[WorkspaceRecord]
    total:int
    page:int
    page_size:int
