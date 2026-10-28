"""Versioned, read-only detail contracts; unavailable telemetry is never fabricated."""
from app.schemas.demo_reports import DemoReport, DemoWan
from datetime import date
from typing import Literal
from app.schemas.subscriber_events import SubscriberHistoryEvent
from pydantic import BaseModel, Field, field_validator, model_validator


class RouterRecord(BaseModel):
    wan_snapshot: DemoWan | None = None
    id: str
    name: str
    management_address: str
    site: str
    model: str
    routeros_version: str
    status: Literal['ONLINE', 'DEGRADED', 'OFFLINE']
    cpu_percent: float
    memory_percent: float
    subscriber_count: int
    uptime: str
    last_seen: str
    is_demo: Literal[True]


class SubscriberRecord(BaseModel):
    can_manage_pppoe: bool = False
    id: str
    access_type: Literal['PPPOE'] | None = None
    router_id: str | None = None
    username: str
    customer_name: str
    router_name: str
    plan: str
    # Read projection only; persisted accounts still require exactly one authority.
    source: Literal['LOCAL', 'RADIUS'] | None = None
    status: Literal['ACTIVE', 'PAUSED', 'PENDING']
    monthly_price: float
    ip_address: str
    joined_at: str
    expires_on: date | None = None
    revision: int = 0
    last_seen: str | None
    is_demo: Literal[True]

    demo_report: DemoReport | None = None

    @model_validator(mode='after')
    def report_identity(self):
        if self.demo_report and (self.demo_report.subscriber_id != self.id or self.demo_report.router_id != self.router_id):
            raise ValueError('Demo report subscriber/router mismatch')
        return self

    @field_validator('source', mode='before')
    @classmethod
    def known_source_or_none(cls, value):
        # Never guess, expose arbitrary input or reject an otherwise readable record.
        return value if isinstance(value, str) and value in ('LOCAL', 'RADIUS') else None


class RouterDetail(BaseModel):
    item: RouterRecord
    assigned_subscribers: list[SubscriberRecord]
    is_demo: Literal[True]


class SubscriberDetail(BaseModel):
    history_available: bool = True
    item: SubscriberRecord
    history: list[SubscriberHistoryEvent] = Field(default_factory=list)
    persistence: Literal['process-memory', 'local-postgresql-demo'] = 'process-memory'
    is_demo: Literal[True]


class SubscriberList(BaseModel):
    items: list[SubscriberRecord]
    total: int
    is_demo: Literal[True]


class QuickResult(BaseModel):
    item_id: str
    success: bool
    result: SubscriberDetail | None = None
    status: int | None = None
    error: str | None = None


class QuickBatchResponse(BaseModel):
    results: list[QuickResult]
    is_demo: Literal[True]
