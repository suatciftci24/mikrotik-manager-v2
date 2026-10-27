"""Explicit, versioned setup for the isolated V2 synthetic schema. Never run on startup."""
import argparse
import json
from pathlib import Path
from sqlalchemy import text
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.schemas.details import SubscriberDetail
from app.schemas.subscriber_events import ExpiryChange
from app.services.demo_data import SUBSCRIBERS
from app.services.demo_subscriptions import request_fingerprint


def validated_snapshots(snapshots):
    clean, ids, event_ids = [], set(), set()
    for raw in snapshots:
        detail = SubscriberDetail.model_validate(raw).model_dump(mode='json')
        item, events = detail['item'], detail['history']
        if not item['id'].startswith('demo-sub-') or item['id'] in ids or item['revision'] != len(events):
            raise ValueError('Invalid or duplicate synthetic subscriber snapshot')
        ids.add(item['id'])
        previous = None
        for revision, event in enumerate(reversed(events), 1):
            if (event['id'] in event_ids or event['source'] != item['source'] or not event['actor_id'].startswith('demo-')
                    or (revision > 1 and event['previous_expires_on'] != previous)):
                raise ValueError('Invalid synthetic history chain')
            event_ids.add(event['id'])
            ExpiryChange.model_validate({'expires_on': event['expires_on'], 'expected_expires_on': event['previous_expires_on'],
                                        'expected_revision': revision-1, 'expected_source': event['source'],
                                        'operation': event['operation'], 'request_id': event['id'], 'confirmed': True})
            previous = event['expires_on']
        if events and item['expires_on'] != previous:
            raise ValueError('Snapshot date and history disagree')
        clean.append(detail)
    return clean


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
            item, events = detail['item'], detail['history']
            connection.execute(text(f'INSERT INTO {schema}.subscribers(id,payload,revision) VALUES (:id,CAST(:payload AS jsonb),:revision)'),
                               {'id': item['id'], 'payload': json.dumps(item), 'revision': item['revision']})
            chronological = list(reversed(events))
            for revision, event in enumerate(chronological, 1):
                connection.execute(text(f'INSERT INTO {schema}.events(id,subscriber_id,revision,payload) VALUES (:id,:subscriber,:revision,CAST(:payload AS jsonb))'),
                                   {'id': event['id'], 'subscriber': item['id'], 'revision': revision, 'payload': json.dumps(event)})
                change = ExpiryChange.model_validate({'expires_on': event['expires_on'], 'expected_expires_on': event['previous_expires_on'],
                                                     'expected_revision': revision-1, 'expected_source': event['source'],
                                                     'operation': event['operation'], 'request_id': event['id'], 'confirmed': True})
                prior_response = adapter._response({**item, 'expires_on': event['expires_on'], 'revision': revision}, list(reversed(chronological[:revision])))
                connection.execute(text(f'INSERT INTO {schema}.requests(id,subscriber_id,fingerprint,response) VALUES (:id,:subscriber,:fingerprint,CAST(:response AS jsonb))'),
                                   {'id': event['id'], 'subscriber': item['id'], 'fingerprint': request_fingerprint(item['id'], event['actor_id'], change), 'response': json.dumps(prior_response)})
    return True


def main():
    parser = argparse.ArgumentParser(description='Explicit local V2 demo schema initialization (never resets existing data)')
    parser.add_argument('command', choices=['init'])
    parser.add_argument('--snapshot', type=Path, help='Optional synthetic memory snapshot to preserve existing edits/history')
    args = parser.parse_args()
    snapshots = json.loads(args.snapshot.read_text()) if args.snapshot else None
    from app.core.database import engine
    try:
        created = initialize_demo(engine, snapshots)
    finally:
        engine.dispose()
    print('V2 synthetic PostgreSQL schema initialized.' if created else 'V2 synthetic schema already exists; no records overwritten.')


if __name__ == '__main__':
    main()
