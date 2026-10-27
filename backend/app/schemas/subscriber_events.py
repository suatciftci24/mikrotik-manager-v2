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

    @field_validator('occurred_at')
    @classmethod
    def event_time_utc(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Demo işlem zamanı saat dilimi içermelidir')
        return value.astimezone(timezone.utc)
