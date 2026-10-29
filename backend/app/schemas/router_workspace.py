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
    @field_validator('management_address')
    @classmethod
    def documentation_only(cls,value):
        if not any(value in IPv4Network(cidr) for cidr in ('192.0.2.0/24','198.51.100.0/24','203.0.113.0/24')):
            raise ValueError('Yalnız sentetik dokümantasyon IPv4 adresleri kullanılabilir.')
        return value
    @field_validator('name','model','site')
    @classmethod
    def clean_text(cls,value):
        if any(ord(c)<32 for c in value):raise ValueError('Kontrol karakteri kabul edilmez.')
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
