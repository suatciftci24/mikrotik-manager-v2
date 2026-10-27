"""Synthetic measurements stored inside the existing demo subscriber JSON payload."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas.router_events import RouterEvent, RouterObservation


class DemoSession(BaseModel):
    id: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    state: Literal['ACTIVE', 'CLOSED', 'UNKNOWN'] = 'UNKNOWN'
    is_demo: Literal[True] = True

    @field_validator('started_at', 'ended_at')
    @classmethod
    def aware(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError('Demo session time requires timezone')
        return value

    @model_validator(mode='after')
    def ordered(self):
        if self.ended_at is not None and (self.started_at is None or self.ended_at < self.started_at):
            raise ValueError('Invalid demo session interval')
        if self.state == 'ACTIVE' and self.ended_at is not None:
            raise ValueError('Active session cannot have an end')
        return self


class DemoTraffic(BaseModel):
    id: str
    measured_at: datetime
    download_bytes: int | None = Field(default=None, ge=0, strict=True)
    upload_bytes: int | None = Field(default=None, ge=0, strict=True)
    is_demo: Literal[True] = True

    @field_validator('measured_at')
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Demo traffic time requires timezone')
        return value


class DemoWan(BaseModel):
    interface: str
    ip: str
    gateway: str
    default_route: str
    is_demo: Literal[True] = True


class DemoReport(BaseModel):
    subscriber_id: str
    router_id: str
    recorded_at: datetime
    sessions: list[DemoSession] = Field(default_factory=list)
    traffic: list[DemoTraffic] = Field(default_factory=list)
    wan_snapshot: DemoWan | None = None
    router_observations: list[RouterObservation] = Field(default_factory=list)
    router_events: list[RouterEvent] = Field(default_factory=list)
    is_demo: Literal[True] = True

    @model_validator(mode='after')
    def identities(self):
        if self.recorded_at.utcoffset() is None:
            raise ValueError('Demo report time requires timezone')
        for records in (self.sessions, self.traffic, self.router_events, self.router_observations):
            if len({record.id for record in records}) != len(records):
                raise ValueError('Duplicate demo report identity')
        if any(event.router_id != self.router_id for event in [*self.router_events, *self.router_observations]):
            raise ValueError('Demo event router mismatch')
        return self
