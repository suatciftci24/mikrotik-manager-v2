"""Read projections of persisted demo subscriber reports, never a second fixture store."""
from app.schemas.details import SubscriberRecord
from app.schemas.router_events import RouterEventList


def router_event_records(items):
    events, ids, available = [], set(), False
    for raw in items:
        item = SubscriberRecord.model_validate(raw)
        if item.demo_report is None:
            continue
        available = True
        for event in item.demo_report.router_events:
            if event.id in ids:
                raise ValueError('Duplicate persisted demo router event')
            ids.add(event.id)
            events.append(event)
    return RouterEventList(items=events, available=available)
