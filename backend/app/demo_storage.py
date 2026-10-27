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


def main():
    parser = argparse.ArgumentParser(description='Explicit local V2 demo schema initialization (never resets existing data)')
    parser.add_argument('command', choices=['init'])
    parser.add_argument('--examples', action='store_true', help='Add missing deterministic demo examples without overwriting existing records')
    parser.add_argument('--snapshot', type=Path, help='Optional synthetic memory snapshot to preserve existing edits/history')
    args = parser.parse_args()
    snapshots = json.loads(args.snapshot.read_text()) if args.snapshot else None
    from app.core.database import engine
    try:
        created = initialize_demo(engine, snapshots)
        if args.examples:
            print(f'Added {seed_examples(engine)} synthetic integration examples.')
    finally:
        engine.dispose()
    print('V2 synthetic PostgreSQL schema initialized.' if created else 'V2 synthetic schema already exists; no records overwritten.')


if __name__ == '__main__':
    main()
