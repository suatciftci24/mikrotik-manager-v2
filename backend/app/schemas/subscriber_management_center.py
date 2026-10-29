"""Daily synthetic operations: explicit source/revision/router and confirmation per item."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from app.schemas.subscriber_center import SyntheticSubscriberCommand

class SubscriberOperation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:UUID
    item_id:str=Field(pattern=r'^demo-managed-sub-[0-9a-f-]{36}$')
    expected_revision:int=Field(ge=1)
    expected_router_id:str=Field(pattern=r'^demo-managed-router-[0-9a-f-]{36}$')
    expected_source:Literal['LOCAL','RADIUS']
    operation:Literal['EDIT','PLAN','STATUS','EXPIRE','EXTEND','ROUTER']
    value:str|None=Field(default=None,max_length=160)
    days:Literal[30,60,90]|None=None
    expected_expires_on:str|None=Field(default=None,max_length=10)
    confirmed:Literal[True]
    _confirmed=field_validator('confirmed',mode='before')(SyntheticSubscriberCommand.explicit.__func__)

class SubscriberOperations(BaseModel):
    model_config=ConfigDict(extra='forbid')
    entries:list[SubscriberOperation]=Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def unique(self):
        if len({e.item_id for e in self.entries})!=len(self.entries) or len({e.request_id for e in self.entries})!=len(self.entries):raise ValueError('Tekrarlanan abone veya istek kimliği.')
        if len(self.entries)>1 and any(e.operation not in ('STATUS','EXTEND') for e in self.entries):raise ValueError('Toplu işlem yalnız hesap durumu veya uzatma içindir.')
        if len({(e.operation,e.days,e.value if e.operation=='STATUS' else None) for e in self.entries})>1:raise ValueError('Toplu işlem türü ve parametreleri aynı olmalı.')
        return self

class OperationReceipt(BaseModel):
    item_id:str
    request_id:str
    success:bool
    recorded:bool
    operation:str
    actor_id:str
    router_id:str|None=None
    previous_router_id:str|None=None
    previous:dict[str,str|None]
    values:dict[str,str|None]
    occurred_at:str
    revision:int
    error:str|None=None

class OperationResults(BaseModel):
    results:list[OperationReceipt]
    is_demo:Literal[True]=True

class OperationHistory(BaseModel):
    items:list[OperationReceipt]
    total:int
    page:int
    page_size:int
    is_demo:Literal[True]=True
