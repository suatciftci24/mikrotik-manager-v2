"""Versioned, read-only detail contracts; unavailable telemetry is never fabricated."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, field_validator


class RouterRecord(BaseModel):
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
    id: str
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
    last_seen: str | None
    is_demo: Literal[True]

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
    item: SubscriberRecord
    is_demo: Literal[True]


class SubscriberList(BaseModel):
    items: list[SubscriberRecord]
    total: int
    is_demo: Literal[True]
