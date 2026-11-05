"""Synthetic API/transaction acceptance; optional disposable PG, never an existing DB."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import asyncio
import json
from urllib.parse import urlencode
from contextlib import AbstractContextManager
from types import SimpleNamespace
import test_subscriber_center as cases
from app.services.subscriber_center import SubscriberWorkspace, legacy_event
from app.services.subscriber_operations import SubscriberOperationsService
from app.schemas.subscriber_center import SubscriberRenewal
from app.schemas.subscriber_management_center import SubscriberOperation
from app.models.router_workspace import RouterWorkspaceRecord as Router, RouterWorkspaceAudit
from app.models.subscriber_workspace import SyntheticSubscriber as Account, SyntheticSubscriberEvent as Event


class ASGIClient(AbstractContextManager):
    """Exercise the complete ASGI middleware/router stack without sockets or HTTP clients."""
    def __init__(self, app):self.app=app
    def __exit__(self,*args):pass
    def request(self,method,path,headers=None,json=None,params=None):
        import json as codec
        body=codec.dumps(json).encode() if json is not None else b''
        scope=dict(type='http',asgi={'version':'3.0','spec_version':'2.4'},http_version='1.1',
            method=method,scheme='http',path=path,raw_path=path.encode(),root_path='',
            query_string=urlencode(params or {}).encode(),server=('testserver',80),client=('127.0.0.1',1),
            headers=[(b'host',b'testserver'),(b'content-type',b'application/json')]+
                [(key.lower().encode(),value.encode()) for key,value in (headers or {}).items()])
        async def run():
            messages=[];received=False
            async def receive():
                nonlocal received
                if not received:
                    received=True
                    return {'type':'http.request','body':body,'more_body':False}
                await asyncio.Event().wait()
            async def send(message):messages.append(message)
            await asyncio.wait_for(self.app(scope,receive,send),timeout=5)
            content=b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
            return SimpleNamespace(status_code=next(m['status'] for m in messages if m['type']=='http.response.start'),
                                   text=content.decode(),json=lambda:codec.loads(content))
        return asyncio.run(run())
    def get(self,path,**kwargs):return self.request('GET',path,**kwargs)
    def post(self,path,**kwargs):return self.request('POST',path,**kwargs)


class Consistency(cases.SubscriberTransactions):
    def test_http_plan_renew_history_permissions_and_rollback(self):
        from app.main import app
        from app.api.v1 import subscriber_center as routes
        from app.core.security import current_demo_user
        today = datetime.now(ZoneInfo('Europe/Istanbul')).date()
        item = self.workspace.save(self.command(expires_on=(today+timedelta(days=4)).isoformat()), 'creator')
        ops = SubscriberOperationsService(self.sessions, lambda s: None)
        actor = {'id': 'synthetic.operator', 'role_code': 'ADMIN', 'can_manage_users': True, 'is_demo': True}
        def command(row, operation, value, days=None):
            return dict(request_id=str(uuid4()), item_id=row.id, expected_revision=row.revision,
                        expected_router_id=row.router_id, expected_source=row.source,
                        expected_expires_on=row.expires_on.isoformat(), operation=operation,
                        value=value, days=days, confirmed=True)
        plan = command(item, 'PLAN', 'Demo 500')
        headers = {'X-V2-Demo-Action': 'subscriber-workspace'}
        old_overrides = dict(app.dependency_overrides)
        app.dependency_overrides[current_demo_user] = lambda: actor
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(old_overrides)))
        with patch.object(routes, 'workspace', self.workspace), patch.object(routes, 'operations', ops), ASGIClient(app) as client:
            path = '/api/v1/subscriber-workspace/management/execute'
            self.assertEqual(client.post(path, json={'entries':[plan]}).status_code, 403)
            actor['role_code'] = 'VIEWER'
            self.assertEqual(client.post(path, headers=headers, json={'entries':[plan]}).status_code, 403)
            actor['role_code'] = 'ADMIN'
            response = client.post(path, headers=headers, json={'entries':[plan]})
            self.assertEqual(response.status_code, 200, response.text)
            receipt = response.json()['results'][0]
            self.assertTrue(receipt['success']);self.assertEqual(receipt['actor_id'], actor['id'])
            self.assertEqual(receipt['previous']['plan'], item.plan)
            self.assertEqual(receipt['values']['expires_on'], item.expires_on.isoformat())
            updated = self.workspace.detail(item.id).item
            target = (updated.expires_on+timedelta(days=30)).isoformat()
            renew = dict(request_id=str(uuid4()), expected_revision=updated.revision,
                         expected_source=updated.source, expected_expires_on=updated.expires_on.isoformat(),
                         expires_on=target, days=30, confirmed=True)
            renewal_path = '/api/v1/subscriber-workspace/'+item.id+'/renew'
            response = client.post(renewal_path, headers=headers, json=renew)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(client.post(renewal_path, headers=headers, json=renew).json(), response.json())
            detail = client.get('/api/v1/subscriber-center/'+item.id).json()
            audit = next(e for e in detail['history'] if e['operation']=='RENEWAL')
            self.assertEqual(audit['previous_expires_on'], item.expires_on.isoformat())
            self.assertEqual(audit['expires_on'], target)
            self.assertEqual(audit['new_values']['plan'], 'Demo 500')
            self.assertEqual(audit['actor_id'], actor['id'])
            self.assertEqual(datetime.fromisoformat(audit['occurred_at']).utcoffset(), timedelta(0))
            central = client.get('/api/v1/subscriber-workspace/management/history', params={'item_id':item.id}).json()
            central_renewal = next(e for e in central['items'] if e['operation']=='RENEWAL')
            self.assertEqual(central_renewal['values'], audit['new_values'])
            self.assertEqual(client.post(path, headers=headers, json={'entries':[plan]}).json()['results'][0], receipt)
            current = self.workspace.detail(item.id).item
            change = command(current, 'PLAN', 'Demo 900')
            with patch.object(ops, 'audit', side_effect=SQLAlchemyError('synthetic audit failure')):
                failed = client.post(path, headers=headers, json={'entries':[change]}).json()['results'][0]
            self.assertFalse(failed['success']);self.assertFalse(failed['recorded'])
            self.assertEqual(self.workspace.detail(item.id).model_dump(mode='json'), detail)
            invalid = {**renew, 'request_id':str(uuid4()), 'confirmed':False}
            self.assertEqual(client.post(renewal_path, headers=headers, json=invalid).status_code, 422)

    def test_unknown_date_custom_confirmation_and_overflow(self):
        today = datetime.now(ZoneInfo('Europe/Istanbul')).date()
        item = self.workspace.save(self.command(expires_on=None), 'creator')
        def renewal(row, **changes):
            return SubscriberRenewal.model_validate(dict(request_id=str(uuid4()), expected_revision=row.revision,
                expected_source=row.source, expected_expires_on=row.expires_on.isoformat() if row.expires_on else None,
                expires_on=(today+timedelta(days=30)).isoformat(), confirmed=True, **changes))
        from app.services.router_workspace import WorkspaceError
        with self.assertRaises(WorkspaceError):self.workspace.renew(item.id,renewal(item,days=30),'actor')
        saved = self.workspace.renew(item.id,renewal(item,days=None),'actor')
        self.assertEqual(saved.expires_on, today+timedelta(days=30))
        item = self.workspace.save(self.command(username='overflow.test',expires_on='9999-12-31'), 'creator')
        baseline = self.workspace.detail(item.id)
        with self.assertRaises(WorkspaceError) as error:self.workspace.renew(item.id,renewal(item,days=30),'actor')
        self.assertEqual(error.exception.status,422)
        command = SubscriberOperation(request_id=uuid4(), item_id=item.id, expected_revision=item.revision,
            expected_router_id=item.router_id, expected_source=item.source, expected_expires_on='9999-12-31',
            operation='EXTEND',value='9999-12-31',days=30,confirmed=True)
        result = SubscriberOperationsService(self.sessions,lambda s:None).execute(command,'actor')
        self.assertFalse(result['success']);self.assertTrue(result['recorded'])
        self.assertEqual(self.workspace.detail(item.id).item,baseline.item)

    def test_database_audit_insert_failure_rolls_back_record_and_retry(self):
        item=self.workspace.save(self.command(),'creator')
        baseline=self.workspace.detail(item.id)
        command=SubscriberOperation(request_id=uuid4(),item_id=item.id,expected_revision=item.revision,
            expected_router_id=item.router_id,expected_source=item.source,operation='PLAN',value='Demo 900',confirmed=True)
        ops=SubscriberOperationsService(self.sessions,lambda s:None)
        def fail(_connection,_cursor,statement,_parameters,_context,_many):
            if statement.lstrip().upper().startswith('INSERT INTO') and 'events' in statement:
                raise SQLAlchemyError('synthetic database audit insert failure')
        event.listen(self.engine,'before_cursor_execute',fail)
        try:
            result=ops.execute(command,'actor')
            self.assertFalse(result['success']);self.assertFalse(result['recorded'])
        finally:event.remove(self.engine,'before_cursor_execute',fail)
        self.assertEqual(self.workspace.detail(item.id),baseline)
        saved=ops.execute(command,'actor')
        self.assertTrue(saved['success']);self.assertEqual(ops.execute(command,'actor'),saved)
        self.assertEqual(len(self.workspace.detail(item.id).history),2)

    def test_legacy_flat_history_merges_safe_context_without_current_account(self):
        entry=dict(operation='RENEWAL',occurred_at='2026-11-05T21:30:00+00:00',actor_id='synthetic.operator',
            previous_plan='Historical 100',plan='Historical 100',previous_expires_on='2026-10-01',expires_on='2026-12-06',
            previous_values={'password':'CANARY'},new_values={'token':'CANARY'})
        projected=legacy_event(entry)
        self.assertEqual(projected['previous_values'],{'plan':'Historical 100','expires_on':'2026-10-01'})
        self.assertEqual(projected['new_values'],{'plan':'Historical 100','expires_on':'2026-12-06'})
        self.assertNotIn('CANARY',str(projected))


class DisposablePostgres(Consistency):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('V2_RUN_DISPOSABLE_SUBSCRIBER_PG')!='1':
            import unittest
            raise unittest.SkipTest('Explicit disposable PostgreSQL opt-in required')
        cls.root=Path(tempfile.mkdtemp(prefix='v26-subscriber-'))
        cls.addClassCleanup(shutil.rmtree,cls.root)
        cls.pg=Path('/usr/lib/postgresql/16/bin');data=cls.root/'data'
        subprocess.run([str(cls.pg/'initdb'),'-D',str(data),'-U','synthetic','--auth=trust'],check=True,stdout=subprocess.DEVNULL)
        # Unix socket only, private temporary directory; no existing cluster or configured URL.
        subprocess.run([str(cls.pg/'pg_ctl'),'-D',str(data),'-l',str(cls.root/'server.log'),
            '-o',"-h '' -p 55439 -k "+str(cls.root),'-w','start'],check=True,stdout=subprocess.DEVNULL)
        cls.addClassCleanup(subprocess.run,[str(cls.pg/'pg_ctl'),'-D',str(data),'-m','fast','-w','stop'],check=True,stdout=subprocess.DEVNULL)
        cls.url=URL.create('postgresql+psycopg',username='synthetic',database='postgres',query={'host':str(cls.root),'port':'55439'})

    def setUp(self):
        self.engine=create_engine(self.url,execution_options={'schema_translate_map':{'v2_router_workspace':None,'v2_subscriber_workspace':None}})
        self.addCleanup(self.engine.dispose)
        from sqlalchemy.schema import BLANK_SCHEMA
        metadata=MetaData()
        for table in (Router.__table__,RouterWorkspaceAudit.__table__,Account.__table__,Event.__table__):
            table.to_metadata(metadata,schema=None,referred_schema_fn=lambda *args:BLANK_SCHEMA)
        metadata.create_all(self.engine)
        self.addCleanup(metadata.drop_all,self.engine)
        self.sessions=sessionmaker(bind=self.engine,expire_on_commit=False)
        self.router_id='demo-managed-router-'+str(uuid4())
        with self.sessions.begin() as session:
            session.add(Router(id=self.router_id,kind='DEMO_ROUTER',revision=1,fields={'name':'Synthetic','model':'Test'}))
        self.workspace=SubscriberWorkspace(self.sessions,lambda s:None)


def load_tests(loader,tests,pattern):
    import unittest
    return unittest.TestSuite(cls(name) for cls in (Consistency,DisposablePostgres)
        for name in Consistency.__dict__ if name.startswith('test_'))
