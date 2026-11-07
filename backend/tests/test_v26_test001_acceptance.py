"""Only v26-test-001: isolated SQLite + socket-free ASGI; no configured DB/device IO."""
from copy import deepcopy
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
import test_subscriber_center as fixtures
from test_v26_subscriber_consistency import ASGIClient as SocketFreeASGIClient
from app.models.subscriber_workspace import SyntheticSubscriber as Account, SyntheticSubscriberEvent as Event
from app.services.subscriber_operations import SubscriberOperationsService


class ASGIClient(SocketFreeASGIClient):
    """Sequential ASGI acceptance: this sandbox cannot return AnyIO worker results.

    Execute the original synchronous dependency/route functions inline; validation,
    middleware, response serialization and authorization remain the real ASGI stack.
    This deliberately makes no thread/concurrency or network transport claim.
    """
    def request(self, *args, **kwargs):
        async def inline(function, *arguments, **keywords):
            return function(*arguments, **keywords)
        with patch('anyio.to_thread.run_sync', inline):
            return super().request(*args, **kwargs)


class Test001Workspace(TestCase):
    setUp = fixtures.SubscriberTransactions.setUp
    command = fixtures.SubscriberTransactions.command

    def prepare(self):
        from app.main import app
        from app.api.v1 import subscriber_center as routes
        from app.core.security import current_demo_user
        from app.core.database import engine as configured_engine
        self.actor = {'id':'synthetic.test001.operator', 'role_code':'ADMIN', 'can_manage_users':True, 'is_demo':True}
        old = dict(app.dependency_overrides)
        app.dependency_overrides[current_demo_user] = lambda: self.actor
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(old)))
        self.ops = SubscriberOperationsService(self.sessions, lambda s:None)
        for target, name, value in [(routes,'workspace',self.workspace),(routes,'operations',self.ops)]:
            p=patch.object(target,name,value);p.start();self.addCleanup(p.stop)
        # A mistaken route to the configured PostgreSQL engine fails before any IO.
        for name in ('connect','begin'):
            p=patch.object(configured_engine,name,side_effect=AssertionError('configured DB forbidden'))
            p.start();self.addCleanup(p.stop)
        self.client=ASGIClient(app)
        self.headers={'X-V2-Demo-Action':'subscriber-workspace'}
        response=self.client.post('/api/v1/subscriber-workspace',headers=self.headers,
            json=self.command(username='v26-test-001',customer_name='V26 Test 001',status='ACTIVE').model_dump(mode='json'))
        self.assertEqual(response.status_code,200,response.text)
        self.item=response.json()
        self.path='/api/v1/subscriber-workspace/management/execute'

    def payload(self,operation,value,**changes):
        row=self.workspace.detail(self.item['id']).item
        return dict(request_id=str(uuid4()),item_id=row.id,operation=operation,value=value,
                    expected_revision=row.revision,expected_router_id=row.router_id,expected_source=row.source,
                    expected_expires_on=row.expires_on.isoformat(),confirmed=True,**changes)

    def snapshot(self):
        with self.sessions() as session:
            accounts=[{c.name:deepcopy(getattr(row,c.name)) for c in Account.__table__.columns}
                      for row in session.scalars(select(Account).order_by(Account.id))]
            events=[{c.name:deepcopy(getattr(row,c.name)) for c in Event.__table__.columns}
                    for row in session.scalars(select(Event).order_by(Event.id))]
        self.assertEqual(len(accounts),1)
        self.assertEqual(accounts[0]['fields']['username'],'v26-test-001')
        return accounts,events

    def test_four_actions_api_database_detail_audit_and_replay(self):
        self.prepare()
        for operation,value,extra in getattr(self, 'acceptance_actions', [
                ('EXTEND','2027-03-03',{'days':30}),('PLAN','Demo 500',{}),
                ('STATUS','PAUSED',{}),('STATUS','ACTIVE',{})]):
            if hasattr(self, 'stage'):
                self.stage = 'TEST001_' + operation + '_' + ('PAUSED' if value == 'PAUSED' else 'ACTIVE' if value == 'ACTIVE' else 'API_DB_DETAIL_AUDIT_REPLAY')
            with self.subTest(operation=operation,value=value):
                before=self.snapshot();old=self.workspace.detail(self.item['id']).item
                command=self.payload(operation,value,**extra)
                response=self.client.post(self.path,headers=self.headers,json={'entries':[command]})
                self.assertEqual(response.status_code,200,response.text)
                receipt=response.json()['results'][0]
                self.assertTrue(receipt['success']);self.assertTrue(receipt['recorded'])
                detail=self.client.get('/api/v1/subscriber-center/'+self.item['id'])
                self.assertEqual(detail.status_code,200,detail.text)
                detail=detail.json();current=detail['item']
                field={'EXTEND':'expires_on','PLAN':'plan','STATUS':'status'}[operation]
                self.assertEqual(current[field],value)
                self.assertEqual(receipt['values'][field],value)
                for keep in {'expires_on','plan','status'}-{field}:
                    self.assertEqual(current[keep],old.model_dump(mode='json')[keep])
                self.assertEqual(current['revision'],old.revision+1)
                accounts,events=self.snapshot()
                self.assertEqual(accounts[0]['fields'][field],value)
                self.assertEqual(accounts[0]['revision'],current['revision'])
                self.assertEqual(len(events),len(before[1])+1)
                event=next(e for e in events if e['id']==command['request_id'])
                self.assertEqual(event['actor_id'],self.actor['id'])
                self.assertEqual(event['operation'],operation)
                self.assertEqual(event['changes']['_management']['receipt'],receipt)
                audit=next(e for e in detail['history'] if e['revision']==current['revision'] and e['operation']==operation)
                self.assertEqual(audit['actor_id'],event['actor_id'])
                self.assertEqual(audit['occurred_at'],event['occurred_at'])
                self.assertEqual(audit['result'],'APPLIED')
                self.assertEqual(audit['new_values'][field],value)
                self.assertEqual(audit['previous_values'][field],old.model_dump(mode='json')[field])
                history=self.client.get('/api/v1/subscriber-workspace/management/history',params={'item_id':self.item['id']})
                self.assertEqual(history.status_code,200)
                self.assertEqual(next(e for e in history.json()['items'] if e['request_id']==command['request_id']),receipt)
                stable=self.snapshot()
                self.assertEqual(self.client.post(self.path,headers=self.headers,json={'entries':[command]}).json(),response.json())
                self.assertEqual(self.snapshot(),stable)

    def test_rejections_and_database_failure_preserve_account_and_audit(self):
        self.prepare();baseline=self.snapshot();command=self.payload('STATUS','PAUSED')
        self.actor['role_code']='VIEWER'
        self.assertEqual(self.client.post(self.path,headers=self.headers,json={'entries':[command]}).status_code,403)
        self.assertEqual(self.snapshot(),baseline);self.actor['role_code']='ADMIN'
        self.assertEqual(self.client.post(self.path,json={'entries':[command]}).status_code,403)
        self.assertEqual(self.snapshot(),baseline)
        for changes in ({'confirmed':False},{'operation':'INVALID'},{'expected_source':'UNKNOWN'}):
            with self.subTest(invalid=changes):
                response=self.client.post(self.path,headers=self.headers,json={'entries':[{**command,**changes}]})
                self.assertEqual(response.status_code,422,response.text);self.assertEqual(self.snapshot(),baseline)
        with patch.object(self.ops,'audit',side_effect=SQLAlchemyError('synthetic test001 audit failure')):
            receipt=self.client.post(self.path,headers=self.headers,json={'entries':[command]}).json()['results'][0]
        self.assertFalse(receipt['success']);self.assertFalse(receipt['recorded'])
        self.assertEqual(self.snapshot(),baseline)
        # A stale request is rejected and recorded as FAILED; account stays byte-identical.
        stale={**command,'request_id':str(uuid4()),'expected_revision':999}
        receipt=self.client.post(self.path,headers=self.headers,json={'entries':[stale]}).json()['results'][0]
        self.assertFalse(receipt['success']);self.assertTrue(receipt['recorded'])
        accounts,events=self.snapshot();self.assertEqual(accounts,baseline[0]);self.assertEqual(len(events),len(baseline[1])+1)
        self.assertEqual(next(e for e in events if e['id']==stale['request_id'])['changes']['_management']['receipt'],receipt)
        stable=self.snapshot()
        self.assertEqual(self.client.post(self.path,headers=self.headers,json={'entries':[stale]}).json()['results'][0],receipt)
        self.assertEqual(self.snapshot(),stable)


class Test001Legacy(TestCase):
    def test_quick_actions_api_detail_audit_and_denials_memory_only(self):
        from app.main import app
        from app.core.security import current_demo_user
        from app.services import demo_subscriptions
        from app.services.demo_data import SUBSCRIBERS,ROUTERS
        from app.core.database import engine as configured_engine
        row={**SUBSCRIBERS[0],'id':'v26-test-001','username':'v26-test-001','customer_name':'V26 Test 001','expires_on':'2027-02-01','status':'ACTIVE'}
        store=demo_subscriptions.DemoSubscriptionStore([row])
        router=next(r for r in ROUTERS if r['name']==row['router_name'])
        actor={'id':'synthetic.test001.operator','role':'Sistem Yöneticisi','role_code':'ADMIN','is_demo':True,
               'permissions':{router['id']:{'can_view':True,'can_manage_pppoe':True,'can_view_reports':True}}}
        old=dict(app.dependency_overrides);app.dependency_overrides[current_demo_user]=lambda:actor
        self.addCleanup(lambda:(app.dependency_overrides.clear(),app.dependency_overrides.update(old)))
        with patch.object(demo_subscriptions,'store',store),patch.object(configured_engine,'connect',side_effect=AssertionError('configured DB forbidden')):
            client=ASGIClient(app);headers={'X-V2-Demo-Action':'expiry'}
            for action,extra in [('EXTEND',{'days':30}),('PLAN',{'plan':'Fiber 500'}),('STATUS',{'status':'PAUSED'}),('STATUS',{'status':'ACTIVE'})]:
                with self.subTest(action=action,extra=extra):
                    before=store.detail(row['id']);item=before['item']
                    target=(max(datetime.now(ZoneInfo('Europe/Istanbul')).date(),datetime.fromisoformat(item['expires_on']).date())+timedelta(days=30)).isoformat()
                    change=dict(action=action,request_id=str(uuid4()),confirmed=True,expected_revision=item['revision'],
                        expected_source=item['source'],expected_expires_on=item['expires_on'],
                        expires_on=target if action=='EXTEND' else item['expires_on'],router_id=router['id'],router_name=router['name'],**extra)
                    payload={'entries':[{'item_id':row['id'],'change':change}]}
                    response=client.post('/api/v1/subscribers/demo-quick',headers=headers,json=payload)
                    self.assertEqual(response.status_code,200,response.text);result=response.json()['results'][0]
                    self.assertTrue(result['success'],result)
                    detail=client.get('/api/v1/subscribers/'+row['id']);self.assertEqual(detail.status_code,200)
                    self.assertEqual(detail.json()['item'],result['result']['item'])
                    current=store.detail(row['id']);self.assertEqual(current['item']['revision'],item['revision']+1)
                    event=next(e for e in current['history'] if e['id']==change['request_id'])
                    self.assertEqual(event['actor_id'],actor['id']);self.assertEqual(event['action'],action)
                    field={'EXTEND':'expires_on','PLAN':'plan','STATUS':'status'}[action]
                    self.assertEqual(current['item'][field],target if action=='EXTEND' else extra[field])
                    self.assertEqual(client.post('/api/v1/subscribers/demo-quick',headers=headers,json=payload).json(),response.json())
                    self.assertEqual(store.detail(row['id']),current)
            baseline=deepcopy(store._state)
            actor['role']='Viewer';actor['role_code']='VIEWER'
            self.assertEqual(client.post('/api/v1/subscribers/demo-quick',headers=headers,json=payload).status_code,403)
            self.assertEqual(store._state,baseline)
            actor['role']='Sistem Yöneticisi';actor['role_code']='ADMIN'
            actor['permissions'][router['id']]['can_manage_pppoe']=False
            self.assertEqual(client.post('/api/v1/subscribers/demo-quick',headers=headers,json=payload).status_code,403)
            self.assertEqual(store._state,baseline)
            actor['permissions'][router['id']]['can_manage_pppoe']=True
            payload['entries'][0]['change']['confirmed']=False
            self.assertEqual(client.post('/api/v1/subscribers/demo-quick',headers=headers,json=payload).status_code,422)
            self.assertEqual(store._state,baseline)
            self.assertEqual([i['username'] for i in store.list_items()],['v26-test-001'])
