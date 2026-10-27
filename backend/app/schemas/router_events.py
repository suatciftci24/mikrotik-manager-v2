"""Read-only synthetic event contract; unavailable source is distinct from zero events."""
from typing import Literal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict


class RouterEvent(BaseModel):
    id: str
    router_id: str
    kind: Literal['INTERNET_DOWN', 'INTERNET_UP', 'WAN_CHANGE']
    occurred_at: str | None = None
    down_event_id: str | None = None
    state: Literal['OPEN', 'RESOLVED', 'UNKNOWN'] = 'UNKNOWN'
    previous_wan: str | None = None
    new_wan: str | None = None
    source: Literal['legacy-demo', 'synthetic-observation'] = 'legacy-demo'
    source_observation_id: str | None = None
    previous_observation_id: str | None = None
    last_observed_at: str | None = None
    duration_verified: bool = True
    is_demo: Literal[True]


class RouterEventList(BaseModel):
    items: list[RouterEvent] = Field(default_factory=list)
    available: bool = False
    is_demo: Literal[True] = True


class RouterObservation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    router_id: str
    observed_at: datetime
    scope: Literal['internet']
    source: Literal['synthetic-observation']
    internet_status: Literal['ONLINE', 'OFFLINE', 'UNKNOWN'] | None = None
    wan_interface: str | None = None
    default_route: str | None = None
    is_demo: Literal[True]

    @field_validator('observed_at')
    @classmethod
    def utc(cls,value):
        if value.utcoffset() is None:
            raise ValueError('Observation time requires timezone')
        return value.astimezone(timezone.utc)

    @field_validator('id','router_id')
    @classmethod
    def synthetic_identity(cls,value):
        if not value.startswith('demo-') or not value.strip():
            raise ValueError('Synthetic observation identity required')
        return value
