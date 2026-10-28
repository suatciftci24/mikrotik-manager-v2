"""Read-only synthetic network analysis contracts; no execution commands."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Domain = Literal['ROUTER', 'WAN', 'IPSEC', 'PPPOE', 'MONITOR', 'DATA', 'CORRELATION']
State = Literal['OPEN', 'UPDATED', 'RECOVERING', 'RESOLVED']


class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    router_id: str
    domain: Domain
    subject_id: str | None = None
    status: Literal['BAD', 'GOOD', 'UNKNOWN']
    observed_at: datetime
    evidence: str
    is_demo: Literal[True] = True

    @field_validator('observed_at')
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Observation must include timezone')
        return value.astimezone(timezone.utc)


class Transition(BaseModel):
    state: State
    occurred_at: datetime
    evidence: str
    observation_ids: list[str]


class Finding(BaseModel):
    id: str
    domain: Domain
    priority: Literal['P1', 'P2', 'P3', 'P4']
    state: State
    title: str
    reason: str
    evidence: str
    affected_router_ids: list[str]
    recommendation: str
    confidence: Literal['HIGH', 'MEDIUM', 'LOW']
    opened_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    history: list[Transition]
    is_demo: Literal[True] = True


class RouterHealth(BaseModel):
    router_id: str
    name: str
    health: Literal['ATTENTION', 'UNKNOWN', 'HEALTHY']
    signals: dict[str, str]
    latest_observed_at: datetime | None = None
    reliability: Literal['CURRENT', 'STALE', 'MISSING']


class Analysis(BaseModel):
    source: str
    generated_at: datetime
    evaluated_at: datetime
    read_only: Literal[True] = True
    is_demo: Literal[True] = True
    health: list[RouterHealth]
    events: list[Finding]
    summary: dict[str, int]
    operational_summary: str
    limitations: list[str] = Field(default_factory=list)
