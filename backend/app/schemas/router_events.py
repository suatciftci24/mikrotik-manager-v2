"""Read-only synthetic event contract; unavailable source is distinct from zero events."""
from typing import Literal
from pydantic import BaseModel, Field


class RouterEvent(BaseModel):
    id: str
    router_id: str
    kind: Literal['INTERNET_DOWN', 'INTERNET_UP', 'WAN_CHANGE']
    occurred_at: str | None = None
    down_event_id: str | None = None
    state: Literal['OPEN', 'UNKNOWN'] = 'UNKNOWN'
    previous_wan: str | None = None
    new_wan: str | None = None
    is_demo: Literal[True]


class RouterEventList(BaseModel):
    items: list[RouterEvent] = Field(default_factory=list)
    available: bool = False
    is_demo: Literal[True] = True
