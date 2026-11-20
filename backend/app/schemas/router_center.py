"""Read-only normalized router center. No credentials, endpoints to execute, or raw payloads."""
from typing import Literal
from app.schemas.router_readonly import ReadOnlySnapshot
from pydantic import BaseModel,ConfigDict

class RouterCenterSummary(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str
    name:str
    identity:str|None=None
    model:str|None=None
    routeros_version:str|None=None
    management_address:str
    site:str|None=None
    inventory_description:str|None=None
    status:str
    management_status:Literal['ACTIVE','INACTIVE']|None=None
    simulated_status:Literal['ONLINE','OFFLINE','UNKNOWN']|None=None
    simulated_last_seen_at:str|None=None
    last_success_at:str|None=None
    last_seen_at:str|None=None
    cpu_percent:float|None=None
    memory_percent:float|None=None
    uptime:str|None=None

class RouterCenterEvent(BaseModel):
    action:str
    occurred_at:str
    actor_id:str
    revision:int|None=None
    record_id:str|None=None
    changes:dict[str,dict[str,str|None]]|None=None

class RouterSubscriberSummary(BaseModel):
    active:int
    paused:int
    other:int
    total:int
    packages:dict[str,int]

class RouterCenterData(BaseModel):
    item:RouterCenterSummary
    source:Literal['PERSISTENT_DEMO','STATIC_DEMO','REGISTERED']
    is_demo:bool
    device_connection_started:Literal[False]=False
    sections:dict[str,Literal['AVAILABLE','UNMEASURED','PREPARING']]
    events:list[RouterCenterEvent]
    read_snapshot:ReadOnlySnapshot|None=None
