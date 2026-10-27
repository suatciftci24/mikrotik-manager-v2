"""Opt-in metadata rollback/reopen proof in the existing disposable V2 schema policy."""
import os
from datetime import datetime, timezone
from unittest import TestCase, skipUnless
from uuid import uuid4
from sqlalchemy import text, event
from app.core.database import engine
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.demo_storage import initialize_demo, seed_examples, process_demo_events


@skipUnless(os.environ.get('V2_RUN_PG_TESTS')=='1','Requires permitted isolated V2 PostgreSQL socket access')
class AlarmAutomationPostgres(TestCase):
    def test_metadata_append_rollback_idempotency_and_reopen_preserve_business_history(self):
        schema='v2_demo_test_'+uuid4().hex
        try:
            initialize_demo(engine,schema=schema);seed_examples(engine,schema=schema)
            store=PostgresDemoStore(engine,schema)
            item=next(item for item in store.list_items() if item.get('demo_report') and item['router_id']=='demo-router-001')
            before=store.detail(item['id'])
            row=dict(id='demo-observation-test-append',router_id=item['router_id'],observed_at=datetime.now(timezone.utc).isoformat(),scope='internet',source='synthetic-observation',internet_status='OFFLINE',wan_interface='wan2',default_route='0.0.0.0/0 via 192.0.2.101',is_demo=True)
            batches=[{'subscriber_id':item['id'],'observations':[row]}]
            def fail(_conn,_cursor,statement,_params,_context,_many):
                if statement.startswith(f'UPDATE {schema}.subscribers'):raise RuntimeError('synthetic metadata rollback')
            event.listen(engine,'before_cursor_execute',fail)
            try:
                with self.assertRaises(RuntimeError):process_demo_events(engine,batches,schema)
            finally:event.remove(engine,'before_cursor_execute',fail)
            self.assertEqual(store.detail(item['id']),before)
            self.assertEqual(process_demo_events(engine,batches,schema),1)
            self.assertEqual(process_demo_events(engine,batches,schema),0)
            saved=PostgresDemoStore(engine,schema).detail(item['id'])
            self.assertEqual(saved['history'],before['history']);self.assertEqual(saved['item']['revision'],before['item']['revision'])
            self.assertEqual(len(saved['item']['demo_report']['router_events']),len(before['item']['demo_report']['router_events'])+1)
        finally:
            with engine.begin() as connection:connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
