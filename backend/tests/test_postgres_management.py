"""Opt-in transaction tests: isolated disposable V2 schemas, no application/device IO."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import os
from unittest import TestCase, skipUnless
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import event, text
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.core.database import engine
from app.demo_storage import initialize_demo
from app.schemas.subscriber_management import SubscriberCreate, SubscriberChange
from app.schemas.subscriber_events import ExpiryChange
from app.services.demo_subscriptions import DemoChangeError, DemoStorageUnavailable


@skipUnless(os.environ.get('V2_RUN_PG_TESTS') == '1', 'Local V2 PostgreSQL integration requires explicit opt-in and socket access')
class PostgresManagement(TestCase):
    def setUp(self):
        self.schema='v2_demo_test_'+uuid4().hex
        self.addCleanup(self.cleanup)
        initialize_demo(engine,schema=self.schema)
        self.store=PostgresDemoStore(engine,self.schema)

    def cleanup(self):
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS {self.schema} CASCADE'))

    def create(self, **changes):
        return SubscriberCreate.model_validate({**dict(customer_name='Sentetik Test',username='demo.new',router_id='demo-router-001',source='LOCAL',plan='Fiber 100',request_id=str(uuid4()),confirmed=True),**changes})

    def change(self,item,operation='PLAN_CHANGE',value='Fiber 500',**changes):
        return SubscriberChange.model_validate({**dict(operation=operation,value=value,expected_value=item['plan' if operation=='PLAN_CHANGE' else 'status'],expected_revision=item['revision'],expected_source=item['source'],request_id=str(uuid4()),confirmed=True),**changes})

    def test_create_reopen_retry_and_mixed_management_expiry_history(self):
        create=self.create();saved=self.store.create_subscriber(create,'demo-user');item=saved['item']
        reopened=PostgresDemoStore(engine,self.schema)
        self.assertEqual(reopened.detail(item['id']),saved)
        self.assertEqual(reopened.create_subscriber(create,'demo-user'),saved)
        command=self.change(item);changed=reopened.change_subscriber(item['id'],command,'demo-user')
        self.assertEqual(reopened.change_subscriber(item['id'],command,'demo-user'),changed)
        paused=reopened.change_subscriber(item['id'],self.change(changed['item'],'STATUS_CHANGE','ACTIVE'),'demo-user')
        expiry=ExpiryChange.model_validate(dict(expires_on=(datetime.now(ZoneInfo('Europe/Istanbul')).date()+timedelta(days=90)).isoformat(),expected_expires_on=None,expected_revision=paused['item']['revision'],expected_source='LOCAL',operation='DATE_EDIT',request_id=str(uuid4()),confirmed=True))
        final=reopened.change_expiry(item['id'],expiry,'demo-user')
        self.assertEqual(final['item']['revision'],4);self.assertEqual(len(final['history']),4)
        self.assertEqual(next(r for r in reopened.list_items() if r['id']==item['id']),final['item'])
        self.assertEqual(final['item']['plan'],'Fiber 500');self.assertEqual(final['item']['status'],'ACTIVE')
        self.assertEqual(final['history'][0]['actor_id'],'demo-user')

    def test_concurrent_creations_cannot_bypass_namespace_or_duplicate_requests(self):
        def attempt(command):
            try:
                return PostgresDemoStore(engine,self.schema).create_subscriber(command,'demo-user')['item']['id']
            except DemoChangeError as error: return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,[self.create(),self.create(username='DEMO.NEW')]))
        self.assertEqual(sum(isinstance(x,str) for x in results),1);self.assertIn(409,results)
        same=self.create(username='demo.retry')
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(attempt,[same,same]))
        self.assertEqual(results[0],results[1]);self.assertEqual(len(self.store.detail(results[0])['history']),1)

    def test_stale_concurrent_updates_and_global_request_collision(self):
        item=self.store.create_subscriber(self.create(),'demo-user')['item']
        def attempt(command):
            try:
                self.store.change_subscriber(item['id'],command,'demo-user');return 200
            except DemoChangeError as error:return error.status_code
        commands=[self.change(item),self.change(item,'STATUS_CHANGE','ACTIVE')]
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,commands))
        self.assertEqual(sorted(results),[200,409]);self.assertEqual(len(self.store.detail(item['id'])['history']),2)
        key=str(uuid4());cmd=self.create(username='demo.collision',request_id=key)
        self.store.create_subscriber(cmd,'demo-user')
        current=self.store.detail(item['id'])['item']
        with self.assertRaises(DemoChangeError):
            self.store.change_subscriber(item['id'],self.change(current,value='Fiber 1000',request_id=key),'demo-user')

    def test_failure_rolls_back_creation_update_event_and_request(self):
        for table in ('events','requests'):
            command=self.create(username='demo.rollback.'+table)
            before=self.store.list_items()
            def fail(_conn,_cursor,statement,_parameters,_context,_many):
                if statement.startswith(f'INSERT INTO {self.schema}.{table}'):
                    raise RuntimeError('synthetic failure')
            event.listen(engine,'before_cursor_execute',fail)
            try:
                with self.assertRaises(RuntimeError):self.store.create_subscriber(command,'demo-user')
            finally:event.remove(engine,'before_cursor_execute',fail)
            self.assertEqual(self.store.list_items(),before)
            saved=self.store.create_subscriber(command,'demo-user');item=saved['item']
            change=self.change(item)
            event.listen(engine,'before_cursor_execute',fail)
            try:
                with self.assertRaises(RuntimeError):self.store.change_subscriber(item['id'],change,'demo-user')
            finally:event.remove(engine,'before_cursor_execute',fail)
            self.assertEqual(self.store.detail(item['id']),saved)
            self.assertEqual(len(self.store.change_subscriber(item['id'],change,'demo-user')['history']),2)

    def test_missing_schema_never_falls_back_and_mixed_snapshot_import_keeps_requests(self):
        absent=PostgresDemoStore(engine,'v2_demo_test_'+uuid4().hex)
        with self.assertRaises(DemoStorageUnavailable):absent.create_subscriber(self.create(),'demo-user')
        command=self.create();saved=self.store.create_subscriber(command,'demo-user')
        change=self.change(saved['item']);saved=self.store.change_subscriber(saved['item']['id'],change,'demo-user')
        other='v2_demo_test_'+uuid4().hex
        try:
            initialize_demo(engine,[saved],schema=other)
            restored=PostgresDemoStore(engine,other)
            self.assertEqual(restored.detail(saved['item']['id']),saved)
            self.assertEqual(restored.change_subscriber(saved['item']['id'],change,'demo-user'),saved)
            self.assertEqual(len(restored.create_subscriber(command,'demo-user')['history']),1)
        finally:
            with engine.begin() as connection:connection.execute(text(f'DROP SCHEMA IF EXISTS {other} CASCADE'))


    def test_pppoe_api_permissions_commands_history_and_list_detail_consistency(self):
        # Use only this test's real, disposable PostgreSQL schema; no memory adapter.
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from app.main import app
        with patch('app.services.demo_subscriptions.store', self.store), TestClient(app) as client:
            create=self.create().model_dump(mode='json')
            headers={'X-V2-Demo-Action':'subscriber-management'}
            self.assertEqual(client.post('/api/v1/subscribers/demo-create',json=create,headers=headers).status_code,401)
            client.post('/api/v1/auth/login',json={'username':'demo','password':'demo-only'})
            self.assertEqual(client.post('/api/v1/subscribers/demo-create',json=create).status_code,403)
            self.assertEqual(client.post('/api/v1/subscribers/demo-create',json={**create,'confirmed':False},headers=headers).status_code,422)
            response=client.post('/api/v1/subscribers/demo-create',json=create,headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            saved=response.json();item_id=saved['item']['id']
            self.assertEqual(saved['persistence'],'local-postgresql-demo')
            self.assertEqual(client.post('/api/v1/subscribers/demo-create',json=create,headers=headers).json(),saved)
            command=self.change(saved['item']).model_dump(mode='json')
            response=client.post(f'/api/v1/subscribers/{item_id}/demo-management',json=command,headers=headers)
            self.assertEqual(response.status_code,200,response.text);saved=response.json()
            self.assertEqual(client.post(f'/api/v1/subscribers/{item_id}/demo-management',json=command,headers=headers).json(),saved)
            for value in ('ACTIVE','PAUSED'):
                command=self.change(saved['item'],'STATUS_CHANGE',value).model_dump(mode='json')
                response=client.post(f'/api/v1/subscribers/{item_id}/demo-management',json=command,headers=headers)
                self.assertEqual(response.status_code,200,response.text);saved=response.json()
                self.assertEqual(saved['item']['status'],value)
            item=saved['item']
            expiry=dict(expires_on=(datetime.now(ZoneInfo('Europe/Istanbul')).date()+timedelta(days=90)).isoformat(),expected_expires_on=None,
                        expected_revision=item['revision'],expected_source='LOCAL',operation='DATE_EDIT',request_id=str(uuid4()),confirmed=True)
            response=client.post(f'/api/v1/subscribers/{item_id}/demo-expiry',json=expiry,headers={'X-V2-Demo-Action':'expiry'})
            self.assertEqual(response.status_code,200,response.text);saved=response.json()
            detail=client.get(f'/api/v1/subscribers/{item_id}').json()
            self.assertEqual(saved,detail)
            listed=client.get('/api/v1/subscribers').json()['items']
            self.assertEqual(next(row for row in listed if row['id']==item_id),detail['item'])
            self.assertEqual(detail['item']['plan'],'Fiber 500');self.assertEqual(detail['item']['status'],'PAUSED')
            self.assertEqual(len(detail['history']),5)
            self.assertEqual([e['operation'] for e in detail['history']],['DATE_EDIT','STATUS_CHANGE','STATUS_CHANGE','PLAN_CHANGE','CREATE'])
            self.assertTrue(all(e['actor_id']=='demo-user' and e['is_demo'] and datetime.fromisoformat(e['occurred_at'].replace('Z','+00:00')).utcoffset().total_seconds()==0 for e in detail['history']))
            duplicate=self.create(request_id=str(uuid4())).model_dump(mode='json')
            self.assertEqual(client.post('/api/v1/subscribers/demo-create',json=duplicate,headers=headers).status_code,409)
            unknown=client.get('/api/v1/subscribers/demo-sub-1006').json()['item']
            denied={'operation':'PLAN_CHANGE','value':'Fiber 500','expected_value':unknown['plan'],'expected_revision':unknown['revision'],
                    'expected_source':'LOCAL','request_id':str(uuid4()),'confirmed':True}
            self.assertEqual(client.post('/api/v1/subscribers/demo-sub-1006/demo-management',json=denied,headers=headers).status_code,409)
            self.assertEqual(client.get('/api/v1/subscribers/demo-sub-1006').json()['history'],[])
            client.post('/api/v1/auth/logout')
