"""Only public read-only telemetry; no account names or credentials can cross this DTO."""
from datetime import datetime,timezone
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator
class InterfaceSnapshot(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(alias='.id',max_length=80)
    name:str=Field(max_length=160)
    type:str=Field(max_length=160)
    disabled:bool
    running:bool
class DefaultRouteSnapshot(BaseModel):
    model_config=ConfigDict(extra='forbid')
    destination:Literal['0.0.0.0/0']=Field(alias='dst-address')
    gateway:str=Field(max_length=160)
    active:bool
    disabled:bool
class ReadOnlySnapshot(BaseModel):
    model_config=ConfigDict(extra='forbid')
    identity:Literal['CEBECI_TOWERS']
    model:Literal['RB3011UiAS']
    routeros_version:str=Field(pattern=r'^6\.49\.19(?: \(stable\))?$')
    cpu_percent:int=Field(ge=0,le=100)
    memory_percent:float=Field(ge=0,le=100,allow_inf_nan=False)
    uptime:str=Field(min_length=1,max_length=80)
    captured_at:datetime
    interfaces:list[InterfaceSnapshot]=Field(max_length=128)
    default_routes:list[DefaultRouteSnapshot]=Field(max_length=128)
    wan_ip:None=None
    pppoe_count:int|None=Field(ge=0,le=128)
    pppoe_explicit_count:int=Field(ge=0,le=128)
    ppp_any_count:int=Field(ge=0,le=128)
    hotspot_count:int=Field(ge=0,le=128)
    is_demo:Literal[False]=False
    read_only:Literal[True]=True
    @field_validator('captured_at')
    @classmethod
    def utc(cls,value):
        if value.utcoffset() is None:raise ValueError('UTC timestamp required')
        return value.astimezone(timezone.utc)
