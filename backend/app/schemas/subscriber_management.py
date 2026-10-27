"""Demo-only commands; no credentials or device provisioning parameters."""
from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.subscriber_events import ExpiryChange


class DemoCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_id: UUID
    confirmed: Literal[True]


class SubscriberCreate(DemoCommand):
    customer_name: str = Field(min_length=2, max_length=160)
    username: str = Field(min_length=1, max_length=96, pattern=r'^[A-Za-z0-9][A-Za-z0-9._@-]*$')
    router_id: str = Field(min_length=1, max_length=100)
    source: Literal['LOCAL', 'RADIUS']
    plan: str = Field(min_length=1, max_length=120)
    status: Literal['ACTIVE', 'PAUSED'] = 'PAUSED'
    expires_on: date | None = None

    @field_validator('expires_on', mode='before')
    @classmethod
    def calendar_date_only(cls, value):
        return ExpiryChange.calendar_date_only(value)

    @field_validator('customer_name')
    @classmethod
    def printable_name(cls, value):
        if not value.isprintable():
            raise ValueError('Ad yazdırılabilir karakterlerden oluşmalıdır')
        return value


class SubscriberChange(DemoCommand):
    expected_revision: int = Field(ge=0)
    expected_source: Literal['LOCAL', 'RADIUS']
    operation: Literal['PLAN_CHANGE', 'STATUS_CHANGE']
    expected_value: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=120)


class DemoPlan(BaseModel):
    name: str
    monthly_price: float


class DemoRouter(BaseModel):
    id: str
    name: str


class DemoOptions(BaseModel):
    plans: list[DemoPlan]
    routers: list[DemoRouter]
    is_demo: Literal[True]
    persistence: Literal['local-postgresql-demo']
