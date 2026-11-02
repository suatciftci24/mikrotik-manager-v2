"""Offline, allowlisted V1 inventory handoff. No DB, HTTP or router transport."""
import os
import stat
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime

MAX_BYTES = 1024 * 1024

class InventoryRow(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    identity: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    routeros_version: str | None = Field(default=None, max_length=50)
    sampled_at: AwareDatetime | None = None
    cpu_load_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    memory_used_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

class HealthSample(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    router_id: str = Field(pattern=r'^[1-9][0-9]*$', max_length=19)
    id: str = Field(pattern=r'^[1-9][0-9]*$', max_length=19)
    sampled_at: AwareDatetime
    cpu_load_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    memory_used_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    internet_success: bool | None = None

class InventoryFile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: Literal['V1_INVENTORY_EXPORT']
    items: list[InventoryRow] = Field(max_length=2000)
    health_samples: list[HealthSample] = Field(default_factory=list, max_length=2000)

class InventoryUnavailable(Exception):
    pass

def read_inventory():
    path = os.environ.get('V2_V1_INVENTORY_FILE')
    if not path:
        return dict(source='V1_INVENTORY_EXPORT', is_demo=False, availability='NO_DATA', items=[])
    try:
        if not os.path.isabs(path):
            raise ValueError('Absolute path required')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES or info.st_nlink != 1:
                raise ValueError('Invalid handoff')
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Oversized handoff')
        data = InventoryFile.model_validate_json(raw)
        if len({row.id for row in data.items}) != len(data.items):
            raise ValueError('Duplicate IDs')
        now = datetime.now(timezone.utc)
        # Export supplies at most one latest sample per immutable V1 primary key.
        health = {}
        router_ids = {row.id for row in data.items}
        for sample in data.health_samples:
            if sample.router_id not in router_ids or sample.router_id in health or sample.sampled_at > now:
                raise ValueError('Unmatched, duplicate or future health sample')
            health[sample.router_id] = sample
        items = []
        for row in data.items:
            if row.sampled_at and row.sampled_at > now:
                raise ValueError('Future observation')
            item = row.model_dump(mode='json')
            sample = health.get(row.id)
            item['health_source'] = 'V1_ROUTER_HEALTH_SAMPLES' if sample else None
            item['health_sample_id'] = sample.id if sample else None
            item['connection_status'] = 'NO_DATA'
            if sample:
                for field in ('sampled_at', 'cpu_load_percent', 'memory_used_percent'):
                    item[field] = sample.model_dump(mode='json')[field]
                item['connection_status'] = ('LAST_PROBE_SUCCEEDED' if sample.internet_success else 'LAST_PROBE_FAILED') if sample.internet_success is not None else 'NO_DATA'
            measured_at = sample.sampled_at if sample else row.sampled_at
            # Inventory timestamps, WAN state and enabled flags never prove online status.
            item['status'] = 'NO_DATA'
            item['freshness'] = ('STALE' if (now-measured_at).total_seconds() > 300 else 'RECENT') if measured_at else 'NO_DATA'
            if measured_at is None:
                item['cpu_load_percent'] = item['memory_used_percent'] = None
            items.append(item)
        return dict(source=data.source, is_demo=False, availability='AVAILABLE' if items else 'NO_DATA', items=items)
    except (OSError, ValueError, TypeError):
        raise InventoryUnavailable() from None
