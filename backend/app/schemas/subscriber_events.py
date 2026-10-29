from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExpiryChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expires_on: date
    expected_expires_on: date | None
    expected_revision: int = Field(ge=0)
    expected_source: Literal['LOCAL', 'RADIUS']
    operation: Literal['RENEWAL', 'DATE_EDIT']
    request_id: UUID
    confirmed: Literal[True]

    @field_validator('expires_on', 'expected_expires_on', mode='before')
    @classmethod
    def calendar_date_only(cls, value):
        if value is None:
            return value
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('Tarih YYYY-MM-DD biçiminde olmalıdır')
        return value


class SubscriberHistoryEvent(BaseModel):
    id: str
    occurred_at: datetime
    previous_expires_on: date | None = None
    expires_on: date | None = None
    previous_values: dict[str, str | float | None] = Field(default_factory=dict)
    new_values: dict[str, str | float | None] = Field(default_factory=dict)
    operation: Literal['RENEWAL', 'DATE_EDIT', 'CREATE', 'PLAN_CHANGE', 'STATUS_CHANGE']
    source: Literal['LOCAL', 'RADIUS']
    actor_id: str
    is_demo: Literal[True]

    action: str | None = None
    previous_plan: str | None = None
    plan: str | None = None
    previous_status: str | None = None
    status: str | None = None
    router_name: str | None = None
    router_id: str | None = None
    subscriber_id: str | None = None

    @field_validator('occurred_at')
    @classmethod
    def event_time_utc(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Demo işlem zamanı saat dilimi içermelidir')
        return value.astimezone(timezone.utc)


class QuickChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['EXTEND', 'PLAN', 'STATUS', 'CREATE']
    request_id: UUID
    confirmed: Literal[True]
    expected_revision: int = Field(ge=0)
    expected_source: Literal['LOCAL', 'RADIUS']
    expected_expires_on: date | None
    expires_on: date | None
    days: Literal[7, 15, 30, 60, 90] | None = None
    plan: str = Field(default='', max_length=80)
    status: Literal['ACTIVE', 'PAUSED'] = 'ACTIVE'
    router_id: str = Field(min_length=1, max_length=100)
    router_name: str = Field(min_length=1, max_length=100)
    username: str = Field(default='', max_length=80, pattern=r'^[a-zA-Z0-9_.-]*$')
    customer_name: str = Field(default='', max_length=120)

    @field_validator('expires_on', 'expected_expires_on', mode='before')
    @classmethod
    def calendar_date_only(cls, value):
        return ExpiryChange.calendar_date_only(value)


class QuickEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_id: str = Field(min_length=1, max_length=100)
    change: QuickChange


class QuickBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    entries: list[QuickEntry] = Field(min_length=1, max_length=100)
