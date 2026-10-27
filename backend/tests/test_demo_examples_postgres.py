"""Real persistence opt-in; same disposable schema policy as existing V2 tests."""
import os
from unittest import TestCase, skipUnless
from uuid import uuid4
from sqlalchemy import text
from app.core.database import engine
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.demo_storage import initialize_demo, seed_examples
from app.schemas.subscriber_management import SubscriberChange


@skipUnless(os.environ.get('V2_RUN_PG_TESTS') == '1', 'Requires permitted isolated V2 PostgreSQL socket access')
class DemoExamplesPostgres(TestCase):
    def test_additive_seed_reopen_and_user_edit_survive_reseed(self):
        schema = 'v2_demo_test_' + uuid4().hex
        try:
            initialize_demo(engine, schema=schema)
            self.assertEqual(seed_examples(engine, schema), 2)
            store = PostgresDemoStore(engine, schema)
            item = next(item for item in store.list_items() if item.get('demo_report'))
            command = SubscriberChange.model_validate(dict(operation='STATUS_CHANGE',value='PAUSED',expected_value=item['status'],expected_revision=item['revision'],expected_source=item['source'],request_id=str(uuid4()),confirmed=True))
            changed = store.change_subscriber(item['id'], command, 'demo-user')
            self.assertEqual(seed_examples(engine, schema), 0)
            self.assertEqual(PostgresDemoStore(engine,schema).detail(item['id']), changed)
            self.assertEqual(len(store.list_items()), 9)
        finally:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
