"""Explicit, versioned setup for the isolated V2 synthetic schema. Never run on startup."""
import argparse
import json
from pathlib import Path
from sqlalchemy import text
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.schemas.details import SubscriberDetail
from app.schemas.subscriber_events import ExpiryChange
from app.schemas.subscriber_management import SubscriberCreate, SubscriberChange
from app.services.demo_data import SUBSCRIBERS
from app.services.demo_subscriptions import request_fingerprint


def validated_snapshots(snapshots):
    clean, ids, event_ids = [], set(), set()
    for raw in snapshots:
        detail = SubscriberDetail.model_validate(raw).model_dump(mode='json', exclude_unset=True)
        detail.setdefault('history', [])
        item, events = detail['item'], detail['history']
        for key, value in (('revision', 0), ('source', None), ('expires_on', None)):
            item.setdefault(key, value)
        if not item['id'].startswith('demo-sub-') or item['id'] in ids or item['revision'] != len(events):
            raise ValueError('Invalid or duplicate synthetic subscriber snapshot')
        ids.add(item['id'])
        for _before, _after, event, _command, _target in snapshot_steps(detail):
            if event['id'] in event_ids:
                raise ValueError('Duplicate synthetic history event')
            event_ids.add(event['id'])
        clean.append(detail)
    return clean


def snapshot_steps(detail):
    """Validate mixed history backwards and reconstruct exact idempotent responses."""
    state = dict(detail['item'])
    reverse_steps = []
    for event in detail['history']:
        revision = state['revision']
        if revision < 1 or event['source'] != state['source'] or not event['actor_id'].startswith('demo-'):
            raise ValueError('Invalid synthetic history chain')
        operation = event['operation']
        common = {'request_id': event['id'], 'confirmed': True}
        target = state['id']
        if operation in ('RENEWAL', 'DATE_EDIT'):
            if state['expires_on'] != event['expires_on']:
                raise ValueError('Snapshot date and history disagree')
            command = ExpiryChange.model_validate({**common, 'operation': operation, 'expires_on': event['expires_on'],
                       'expected_expires_on': event['previous_expires_on'], 'expected_revision': revision-1, 'expected_source': event['source']})
            before = {**state, 'expires_on': event['previous_expires_on'], 'revision': revision-1}
        else:
            values, previous = event['new_values'], event['previous_values']
            required = {'plan', 'monthly_price'} if operation == 'PLAN_CHANGE' else {'status'}
            if operation == 'CREATE':
                required = {'username', 'customer_name', 'router_name', 'source', 'plan', 'monthly_price', 'status', 'expires_on', 'access_type'}
            if set(values) != required or any(state.get(key) != value for key, value in values.items()):
                raise ValueError('Snapshot values and history disagree')
            if operation == 'CREATE':
                if revision != 1 or previous or state.get('access_type') != 'PPPOE':
                    raise ValueError('Invalid creation history')
                command = SubscriberCreate.model_validate({**common, **{key:values[key] for key in ('username','customer_name','source','plan','status','expires_on')}, 'router_id':state.get('router_id')})
                if state['id'] != 'demo-sub-' + str(command.request_id):
                    raise ValueError('Creation identity mismatch')
                target, before = 'create-subscriber', None
            else:
                if set(previous) != required:
                    raise ValueError('Incomplete previous values')
                field = 'plan' if operation == 'PLAN_CHANGE' else 'status'
                command = SubscriberChange.model_validate({**common, 'operation': operation, 'value': values[field],
                           'expected_value': previous[field], 'expected_revision': revision-1, 'expected_source':event['source']})
                before = {**state, **previous, 'revision': revision-1}
        reverse_steps.append((before, dict(state), event, command, target))
        state = before
        if state is None and len(reverse_steps) != len(detail['history']):
            raise ValueError('Creation must be first history event')
    return list(reversed(reverse_steps))


def insert_snapshot(connection, adapter, detail, schema):
    detail.setdefault('history', [])
    item, events = detail['item'], detail['history']
    for key, value in (('revision', 0), ('source', None), ('expires_on', None)):
        item.setdefault(key, value)
    connection.execute(text(f'INSERT INTO {schema}.subscribers(id,payload,revision) VALUES (:id,CAST(:payload AS jsonb),:revision)'),
                       {'id': item['id'], 'payload': json.dumps(item), 'revision': item['revision']})
    chronological = list(reversed(events))
    for revision, event in enumerate(chronological, 1):
        connection.execute(text(f'INSERT INTO {schema}.events(id,subscriber_id,revision,payload) VALUES (:id,:subscriber,:revision,CAST(:payload AS jsonb))'),
                           {'id': event['id'], 'subscriber': item['id'], 'revision': revision, 'payload': json.dumps(event)})
    for _before, after, event, change, target in snapshot_steps(detail):
        revision = after['revision']
        prior_response = adapter._response(after, list(reversed(chronological[:revision])))
        connection.execute(text(f'INSERT INTO {schema}.requests(id,subscriber_id,fingerprint,response) VALUES (:id,:subscriber,:fingerprint,CAST(:response AS jsonb))'),
                           {'id': event['id'], 'subscriber': item['id'], 'fingerprint': request_fingerprint(target, event['actor_id'], change), 'response': json.dumps(prior_response)})


def initialize_demo(engine, snapshots=None, schema='v2_demo'):
    adapter = PostgresDemoStore(engine, schema)  # Validate destination before any connection.
    if snapshots is None:
        snapshots = [{'item': {**row, 'revision': 0}, 'history': [], 'is_demo': True} for row in SUBSCRIBERS]
    snapshots = validated_snapshots(snapshots)
    migration = Path(__file__).resolve().parents[2] / 'migrations' / 'versions' / '002_demo_storage.sql'
    with engine.begin() as connection:
        # Serialize explicit setup attempts without changing an existing schema.
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext(:name))"), {'name': schema})
        exists = connection.execute(text('SELECT to_regnamespace(:schema)'), {'schema': schema}).scalar_one()
        if exists:
            adapter._verify(connection)
            return False
        for statement in migration.read_text().replace('v2_demo', schema).split(';'):
            if statement.strip():
                connection.execute(text(statement))
        for detail in snapshots:
            insert_snapshot(connection, adapter, detail, schema)
    return True


def seed_examples(engine, schema='v2_demo'):
    from app.services.demo_examples import demo_examples
    from app.services.demo_management import calculate_create
    from app.services.demo_subscriptions import DemoChangeError
    adapter = PostgresDemoStore(engine, schema)
    snapshots = validated_snapshots(demo_examples())
    added = 0
    with engine.begin() as connection:
        adapter._verify(connection)
        connection.execute(text(f'LOCK TABLE {schema}.subscribers IN SHARE ROW EXCLUSIVE MODE'))
        for detail in snapshots:
            if adapter._item(connection, detail['item']['id']) is not None:
                continue  # Preserve all user edits, measurements and history on seeded IDs.
            command = snapshot_steps(detail)[0][3]
            items = list(connection.execute(text(f'SELECT payload FROM {schema}.subscribers')).scalars())
            try:
                calculate_create(command, 'demo-seed', items)
            except DemoChangeError as error:
                if error.status_code == 409:
                    continue  # Existing usernames also belong to the user.
                raise
            insert_snapshot(connection, adapter, detail, schema)
            added += 1
    return added


def process_demo_events(engine, batches=(), schema='v2_demo'):
    """Explicit metadata transaction; no account revision/audit/request rows are reset."""
    from app.schemas.demo_reports import DemoReport
    from app.services.alarm_automation import process_report
    adapter=PostgresDemoStore(engine,schema)
    updates={}
    for batch in batches:
        if set(batch)!={'subscriber_id','observations'} or not batch['subscriber_id'].startswith('demo-sub-') or not isinstance(batch['observations'],list):
            raise ValueError('Synthetic subscriber observation batch required')
        updates.setdefault(batch['subscriber_id'],[]).extend(batch['observations'])
    changed=0
    with engine.begin() as connection:
        adapter._verify(connection)
        connection.execute(text(f'LOCK TABLE {schema}.subscribers IN SHARE ROW EXCLUSIVE MODE'))
        items=list(connection.execute(text(f'SELECT payload FROM {schema}.subscribers')).scalars())
        missing=set(updates)-{item['id'] for item in items}
        if missing:
            raise ValueError('Observation target subscriber not found')
        # Plan all updates before the first write; transaction also protects failures during writes.
        planned=[]
        owners={}
        for item in items:
            if not item.get('demo_report'):
                if item['id'] in updates:
                    raise ValueError('Target requires a persisted demo report')
                continue
            report=DemoReport.model_validate(item['demo_report'])
            if report.subscriber_id!=item['id'] or report.router_id!=item.get('router_id'):
                raise ValueError('Persisted report identity mismatch')
            if report.router_observations or updates.get(item['id']):
                if report.router_id in owners:
                    raise ValueError('A router must have one observation owner')
                owners[report.router_id]=item['id']
                processed=process_report(report,updates.get(item['id'],()))
                if processed!=report:
                    planned.append({**item,'demo_report':processed.model_dump(mode='json')})
        for item in planned:
            connection.execute(text(f'UPDATE {schema}.subscribers SET payload=CAST(:payload AS jsonb) WHERE id=:id'),{'id':item['id'],'payload':json.dumps(item)})
            changed+=1
    return changed


def prepare_alarm_acceptance():
    """Explicit local acceptance setup; adds one unique initial synthetic snapshot only."""
    from uuid import uuid4
    from copy import deepcopy
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from app.core.database import engine
    from app.services.demo_data import ROUTERS
    from app.adapters.alarm_actions import initialize
    adapter=PostgresDemoStore(engine)
    initialize(adapter)  # same repo/marker/cluster checks as explicit alarms-init
    token=str(uuid4())
    item=deepcopy(SUBSCRIBERS[0])
    item.update(id='demo-sub-'+token,username='alarm.accept.'+token,customer_name='SENTETİK Alarm Kabul '+token[:8],
        source='LOCAL',status='PAUSED',access_type='PPPOE',router_id=ROUTERS[0]['id'],router_name=ROUTERS[0]['name'],
        expires_on=(datetime.now(ZoneInfo('Europe/Istanbul')).date()-timedelta(days=1)).isoformat(),revision=0,last_seen=None)
    item.pop('demo_report',None)
    detail=validated_snapshots([dict(item=item,history=[],is_demo=True)])[0]
    with engine.begin() as connection:
        adapter._verify(connection)
        insert_snapshot(connection,adapter,detail,'v2_demo')
    return item['id']


def main():
    parser = argparse.ArgumentParser(description='Explicit local V2 demo setup and synthetic event processing (never resets records)')
    parser.add_argument('command', choices=['init','process-events','alarms-init'])
    parser.add_argument('--observations', type=Path, help='Optional JSON batches: subscriber_id and observations; synthetic append-only input')
    parser.add_argument('--examples', action='store_true', help='Add missing deterministic demo examples without overwriting existing records')
    parser.add_argument('--snapshot', type=Path, help='Optional synthetic memory snapshot to preserve existing edits/history')
    args = parser.parse_args()
    if args.command=='alarms-init' and (args.examples or args.snapshot or args.observations):
        parser.error('alarms-init ek veri/seed argümanı kabul etmez')
    if args.command=='process-events' and (args.examples or args.snapshot):
        parser.error('process-events accepts only --observations')
    if args.command=='init' and args.observations:
        parser.error('--observations requires process-events')
    snapshots = json.loads(args.snapshot.read_text()) if args.snapshot else None
    from app.core.database import engine
    try:
        if args.command=='alarms-init':
            from app.adapters.alarm_actions import initialize
            initialize(PostgresDemoStore(engine))
            print('V2 alarm action schema ready; subscribers and source events unchanged.')
            return
        if args.command=='process-events':
            batches=json.loads(args.observations.read_text()) if args.observations else []
            if not isinstance(batches,list):
                raise ValueError('Observation batches must be a list')
            print(f'Updated {process_demo_events(engine,batches)} synthetic alarm reports.')
            return
        created = initialize_demo(engine, snapshots)
        if args.examples:
            print(f'Added {seed_examples(engine)} synthetic integration examples.')
    finally:
        engine.dispose()
    print('V2 synthetic PostgreSQL schema initialized.' if created else 'V2 synthetic schema already exists; no records overwritten.')


if __name__ == '__main__':
    main()
