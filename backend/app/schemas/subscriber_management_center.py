"""Daily synthetic operations: explicit source/revision/router and confirmation per item."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from app.schemas.subscriber_center import SyntheticSubscriberCommand,SubscriberRequestAudit

class SubscriberOperation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:UUID
    item_id:str=Field(pattern=r'^demo-managed-sub-[0-9a-f-]{36}$')
    expected_revision:int=Field(ge=1)
    expected_router_id:str=Field(pattern=r'^demo-managed-router-[0-9a-f-]{36}$')
    expected_source:Literal['LOCAL','RADIUS']
    operation:Literal['EDIT','PLAN','STATUS','EXPIRE','EXTEND','ROUTER']
    package_id:str|None=Field(default=None,pattern=r'^demo-package-[0-9a-f-]{36}$')
    package_revision:int|None=Field(default=None,ge=1)
    value:str|None=Field(default=None,max_length=160)
    days:int|None=Field(default=None,strict=True,ge=1,le=365)
    expected_expires_on:str|None=Field(default=None,max_length=10)
    expected_status:Literal['ACTIVE','PAUSED']|None=None
    confirmed:Literal[True]
    @model_validator(mode='after')
    def package_selection(self):
        if bool(self.package_id)!=(self.package_revision is not None):raise ValueError('Paket kimliği ve revizyonu birlikte gerekli.')
        if self.package_id and self.operation!='PLAN':raise ValueError('Paket seçimi yalnız PLAN işleminde kullanılır.')
        if self.expected_status is not None and self.operation!='STATUS':raise ValueError('Beklenen hesap durumu yalnız STATUS işleminde kullanılır.')
        return self
    _confirmed=field_validator('confirmed',mode='before')(SyntheticSubscriberCommand.explicit.__func__)

class SubscriberOperations(BaseModel):
    model_config=ConfigDict(extra='forbid')
    entries:list[SubscriberOperation]=Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def unique(self):
        if len({e.item_id for e in self.entries})!=len(self.entries) or len({e.request_id for e in self.entries})!=len(self.entries):raise ValueError('Tekrarlanan abone veya istek kimliği.')
        if len(self.entries)>1 and any(e.operation not in ('STATUS','EXTEND','PLAN') for e in self.entries):raise ValueError('Toplu işlem yalnız hesap durumu, uzatma veya paket değişikliği içindir.')
        if len(self.entries)>1 and any(e.operation=='PLAN' and not e.package_id for e in self.entries):raise ValueError('Toplu paket değişikliği için kayıtlı paket ve revizyon seçin.')
        if len({(e.operation,e.days,e.value if e.operation in ('STATUS','PLAN') else None,e.package_id,e.package_revision) for e in self.entries})>1:raise ValueError('Toplu işlem türü ve parametreleri aynı olmalı.')
        return self

class OperationReceipt(BaseModel):
    source:Literal['LOCAL','RADIUS']|None=None
    item_id:str
    request_id:str
    success:bool
    recorded:bool
    skipped:bool=False
    execution_type:Literal['SINGLE','BULK']|None=None
    group_id:UUID|None=None
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

class OperationHistoryItem(OperationReceipt):
    subscriber_name:str|None=None
    subscriber_username:str|None=None
    actor_username:str|None=None

class OperationHistoryCounts(BaseModel):
    success:int
    failed:int
    skipped:int

class OperationGroupCounts(OperationHistoryCounts):
    group_id:UUID
    total:int

class OperationHistory(BaseModel):
    items:list[OperationHistoryItem]
    total:int
    page:int
    page_size:int
    counts:OperationHistoryCounts|None=None
    groups:list[OperationGroupCounts]=Field(default_factory=list)
    is_demo:Literal[True]=True


class OperationRequestResult(BaseModel):
    request_id:UUID
    status:Literal['SUCCESS','FAILED','SKIPPED','UNKNOWN']
    response:OperationReceipt|None=None
    audit:SubscriberRequestAudit|None=None


class UndoPreviewValue(BaseModel):
    field:str
    previous:str|None
    applied:str|None
    current:str|None


class OperationUndoPreview(BaseModel):
    request_id:UUID
    item_id:str
    audit_revision:int
    current_revision:int
    status:Literal['ELIGIBLE','CONFLICT','INELIGIBLE']
    reason:str
    changes:list[UndoPreviewValue]
    is_demo:Literal[True]=True
