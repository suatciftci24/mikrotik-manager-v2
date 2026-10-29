"""Read-only normalized router center. No credentials, endpoints to execute, or raw payloads."""
from typing import Literal
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
    status:str
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

class RouterCenterData(BaseModel):
    item:RouterCenterSummary
    source:Literal['PERSISTENT_DEMO','STATIC_DEMO','REGISTERED']
    is_demo:bool
    device_connection_started:Literal[False]=False
    sections:dict[str,Literal['AVAILABLE','UNMEASURED','PREPARING']]
    events:list[RouterCenterEvent]
