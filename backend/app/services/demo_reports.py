"""Read projections of persisted demo subscriber reports, never a second fixture store."""
from app.services.alarm_automation import process_report
from app.schemas.details import SubscriberRecord
from app.schemas.router_events import RouterEventList


def router_event_records(items):
    events, ids, available = [], set(), False
    observation_owners = set()
    for raw in items:
        item = SubscriberRecord.model_validate(raw)
        if item.demo_report is None:
            continue
        if item.demo_report.router_observations:
            if item.demo_report.router_id in observation_owners:
                raise ValueError('A router must have one observation owner')
            observation_owners.add(item.demo_report.router_id)
        available = True
        for event in process_report(item.demo_report).router_events:
            if event.id in ids:
                raise ValueError('Duplicate persisted demo router event')
            ids.add(event.id)
            events.append(event)
    return RouterEventList(items=events, available=available)
