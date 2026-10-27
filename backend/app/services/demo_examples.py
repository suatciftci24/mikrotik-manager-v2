"""Deterministic additive seed snapshots. Never executed at application startup."""
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo
from app.schemas.subscriber_management import SubscriberCreate, SubscriberChange
from app.schemas.subscriber_events import ExpiryChange
from app.services.demo_management import calculate_create, calculate_management_change
from app.services.demo_subscriptions import calculate_change
from app.schemas.demo_reports import DemoReport


def demo_examples(now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo('Europe/Istanbul')).date()
    key = lambda name: str(uuid5(NAMESPACE_URL, 'mikrotik-manager-v2/demo-integration/v1/' + name))
    stamp = lambda hours: (now - timedelta(hours=hours)).isoformat()
    snapshots = []
    for index, source in enumerate(('LOCAL', 'RADIUS')):
        command = SubscriberCreate.model_validate(dict(customer_name=f'SENTETİK Entegrasyon {index+1}', username=f'demo.integration.{index+1}', source=source,
            router_id=f'demo-router-00{index+1}', plan='Fiber 100', status='PAUSED', expires_on=today.isoformat(), request_id=key(f'create-{index}'), confirmed=True))
        item, event = calculate_create(command, 'demo-seed', [])
        event['occurred_at'] = stamp(4)
        events = [event]
        for operation, value in [('PLAN_CHANGE', 'Fiber 500'), ('STATUS_CHANGE', 'ACTIVE')]:
            field = 'plan' if operation == 'PLAN_CHANGE' else 'status'
            change = SubscriberChange.model_validate(dict(operation=operation, value=value, expected_value=item[field], expected_revision=item['revision'],
                expected_source=source, request_id=key(f'{operation}-{index}'), confirmed=True))
            item, event = calculate_management_change(item, change, 'demo-seed')
            event['occurred_at'] = stamp(3 if operation == 'PLAN_CHANGE' else 2)
            events.insert(0, event)
        change = ExpiryChange.model_validate(dict(operation='RENEWAL', expires_on=(today+timedelta(days=3 if index == 0 else 30)).isoformat(), expected_expires_on=item['expires_on'],
            expected_revision=item['revision'], expected_source=source, request_id=key(f'renew-{index}'), confirmed=True))
        item, event = calculate_change(item, change, 'demo-seed')
        event['occurred_at'] = stamp(1)
        events.insert(0, event)
        router_events = [
            dict(id='demo-outage-'+str(index), router_id=item['router_id'], kind='INTERNET_DOWN', occurred_at=stamp(6), state='OPEN' if index else 'UNKNOWN', is_demo=True),
            dict(id='demo-wan-'+str(index), router_id=item['router_id'], kind='WAN_CHANGE', occurred_at=stamp(5), previous_wan='wan1 / 192.0.2.100', new_wan='wan2 / 192.0.2.101', is_demo=True),
        ]
        if index == 0:
            router_events.append(dict(id='demo-recovery-0', router_id=item['router_id'], kind='INTERNET_UP', occurred_at=stamp(5.5), down_event_id='demo-outage-0', is_demo=True))
        report = DemoReport.model_validate(dict(subscriber_id=item['id'], router_id=item['router_id'], recorded_at=now.isoformat(), is_demo=True,
            sessions=[dict(id=f'demo-session-{index}', started_at=stamp(8), ended_at=stamp(7), state='CLOSED', is_demo=True),
                      dict(id=f'demo-session-open-{index}', started_at=stamp(1), state='ACTIVE', is_demo=True)] if index == 0 else [],
            traffic=[dict(id=f'demo-traffic-{index}-{day}', measured_at=(now-timedelta(days=day, hours=8 if index else 0)).isoformat(), download_bytes=(day+1)*1048576, upload_bytes=(day+1)*524288, is_demo=True) for day in (0, 2, 10)],
            wan_snapshot=dict(interface='wan2',ip='192.0.2.101',gateway='192.0.2.254',default_route='0.0.0.0/0 via 192.0.2.254',is_demo=True), router_events=router_events))
        item['demo_report'] = report.model_dump(mode='json')
        snapshots.append(dict(item=item, history=events, is_demo=True))
    return snapshots
