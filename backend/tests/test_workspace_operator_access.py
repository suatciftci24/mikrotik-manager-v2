"""HTTP authorization + SQL pagination against temporary synthetic SQLite only."""
import os,tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from fastapi import FastAPI
import asyncio,json
from types import SimpleNamespace
from urllib.parse import urlsplit
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.v1 import router_workspace,router_center,dashboard,subscriber_center
from app.core.security import current_demo_user
from app.models.router_workspace import RouterWorkspaceRecord as Record,RouterWorkspaceAudit as Audit
from app.services.router_workspace import RouterWorkspace

class TestClient:
    def __init__(self,app):self.app=app
    def close(self):pass
    def request(self,method,url,**kwargs):
        parsed=urlsplit(url);body=json.dumps(kwargs.get('json')).encode() if 'json' in kwargs else b''
        scope=dict(type='http',asgi={'version':'3.0','spec_version':'2.4'},http_version='1.1',method=method,scheme='http',path=parsed.path,raw_path=parsed.path.encode(),root_path='',query_string=parsed.query.encode(),server=('test',80),client=('127.0.0.1',1),headers=[(b'host',b'test'),(b'content-type',b'application/json')]+[(k.lower().encode(),v.encode()) for k,v in kwargs.get('headers',{}).items()])
        async def run():
            messages=[];received=False
            async def receive():
                nonlocal received
                if not received:
                    received=True;return {'type':'http.request','body':body,'more_body':False}
                await asyncio.Event().wait()
            async def send(message):messages.append(message)
            await asyncio.wait_for(self.app(scope,receive,send),5)
            content=b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
            return SimpleNamespace(headers=dict((k.decode(),v.decode()) for m in messages if m['type']=='http.response.start' for k,v in m.get('headers',[])),status_code=next(m['status'] for m in messages if m['type']=='http.response.start'),text=content.decode(),json=lambda:json.loads(content))
        async def inline_worker(function,*args,**kwargs):return function(*args)
        # Deterministic socket-free ASGI harness; preserve dependency/auth execution.
        with patch('anyio.to_thread.run_sync',inline_worker):return asyncio.run(run())
    def get(self,url,**kwargs):return self.request('GET',url,**kwargs)
    def post(self,url,**kwargs):return self.request('POST',url,**kwargs)


class OperatorAccess(TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'V2_DEPLOYMENT_PROFILE':'v26-isolated-acceptance'});self.env.start();self.addCleanup(self.env.stop)
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        engine=create_engine('sqlite+pysqlite:///'+str(Path(directory.name)/'workspace.db'),connect_args={'check_same_thread':False},execution_options={'schema_translate_map':{'v2_router_workspace':None,'v2_subscriber_workspace':None}});self.addCleanup(engine.dispose)
        Record.__table__.create(engine);Audit.__table__.create(engine)
        from app.models.subscriber_workspace import SyntheticSubscriber,SyntheticSubscriberEvent,SyntheticSubscriberSkip
        SyntheticSubscriber.__table__.create(engine);SyntheticSubscriberEvent.__table__.create(engine);SyntheticSubscriberSkip.__table__.create(engine)
        self.sessions=sessionmaker(bind=engine,expire_on_commit=False)
        self.store=RouterWorkspace(self.sessions,lambda session:None)
        self.allowed='demo-managed-router-b';self.hidden='demo-managed-router-a'
        with self.sessions.begin() as session:
            for id,kind in [(self.hidden,'DEMO_ROUTER'),(self.allowed,'DEMO_ROUTER'),('trust-profile-x','TRUST_PROFILE')]:
                session.add(Record(id=id,kind=kind,revision=1,fields={'name':'V26 Test Router' if id==self.allowed else 'Hidden','model':'Synthetic','management_address':'192.0.2.10','site':''}))
        for module in (router_workspace,router_center):
            p=patch.object(module,'workspace',self.store);p.start();self.addCleanup(p.stop)
        # Dashboard imports the same singleton lazily.
        p=patch('app.services.router_workspace.workspace',self.store);p.start();self.addCleanup(p.stop)
        from app.services.subscriber_center import SubscriberWorkspace
        accounts=SubscriberWorkspace(self.sessions,lambda session:None)
        for target in ('app.services.subscriber_center.workspace','app.api.v1.subscriber_center.workspace'):
            p=patch(target,accounts);p.start();self.addCleanup(p.stop)
        self.user={'id':'synthetic-operator','is_demo':True,'role_code':'OPERATOR','can_manage_users':False,'permissions':{self.allowed:{'can_view':True},self.hidden:{'can_view':False},'demo-router-1':{'can_view':True},'trust-profile-x':{'can_view':True}}}
        app=FastAPI()
        for module in (router_workspace,router_center,dashboard,subscriber_center):app.include_router(module.router,prefix='/api/v1')
        app.dependency_overrides[current_demo_user]=lambda:self.user
        self.client=TestClient(app);self.addCleanup(self.client.close)
    def test_operator_list_detail_center_and_dashboard_share_exact_scope(self):
        response=self.client.get('/api/v1/router-workspace/routers?page_size=1');self.assertEqual(response.status_code,200,response.text)
        data=response.json();self.assertEqual(data['total'],1);self.assertEqual([r['id'] for r in data['items']],[self.allowed])
        self.assertEqual(self.client.get('/api/v1/router-workspace/routers?page=2&page_size=1').json()['items'],[])
        self.assertEqual(self.client.get('/api/v1/router-workspace/routers?query=Hidden').json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/router-workspace/routers/'+self.allowed).status_code,200)
        data=self.client.get('/api/v1/router-center/'+self.allowed).json();self.assertEqual(data['source'],'PERSISTENT_DEMO');self.assertEqual(data['events'],[]);self.assertEqual(data['sections']['pppoe'],'AVAILABLE')
        data=self.client.get('/api/v1/dashboard/summary').json()['summary'];self.assertEqual(data['router_count'],1);self.assertEqual(data['subscribers_total'],0)
    def test_grouped_subscriber_filters_do_not_count_hidden_router_accounts(self):
        from app.models.subscriber_workspace import SyntheticSubscriber
        with self.sessions.begin() as session:
            for suffix,router in [('visible',self.allowed),('hidden',self.hidden)]:
                fields=dict(username=suffix,customer_name=suffix,router_id=router,access_type='PPPOE',source='LOCAL',plan='Test',status='ACTIVE',expires_on=None)
                session.add(SyntheticSubscriber(id='demo-managed-sub-'+suffix,router_id=router,username_key=suffix,access_type='PPPOE',source='LOCAL',revision=1,fields=fields))
        response=self.client.get('/api/v1/subscriber-workspace?grouped=true&source=LOCAL&expiry_group=UNKNOWN')
        self.assertEqual(response.status_code,200,response.text)
        data=response.json();self.assertEqual(data['total'],1)
        self.assertEqual(data['expiry_groups']['UNKNOWN'],1)
        self.assertEqual([row['username'] for row in data['items']],['visible'])
        data=self.client.get('/api/v1/subscriber-workspace?grouped=true&query=hidden').json()
        self.assertEqual(data['total'],0);self.assertEqual(sum(data['expiry_groups'].values()),0)
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace?grouped=true&source=RADIUS').json()['total'],0)

    def test_foreign_ids_and_revoked_grants_are_denied_before_read(self):
        for id in (self.hidden,'demo-managed-router-missing','trust-profile-x','demo-router-1'):
            self.assertEqual(self.client.get('/api/v1/router-workspace/routers/'+id).status_code,404)
        self.assertEqual(self.client.get('/api/v1/router-center/'+self.hidden).status_code,404)
        self.user['permissions']={}
        self.assertEqual(self.client.get('/api/v1/router-workspace/routers').json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/dashboard/summary').json()['summary']['router_count'],0)
        self.assertEqual(self.client.get('/api/v1/router-center/'+self.allowed).status_code,404)
    def test_mutations_profiles_and_subscriber_management_stay_admin_only(self):
        from uuid import uuid4
        command={'request_id':str(uuid4()),'fields':{'name':'Synthetic','management_address':'192.0.2.10'},'expected_revision':1,'confirmed':True}
        with patch.object(self.store,'save',side_effect=AssertionError('write dispatched')),patch.object(self.store,'delete',side_effect=AssertionError('delete dispatched')):
            for path,payload in [('/routers',command),('/routers/'+self.allowed,command),('/routers/'+self.allowed+'/delete',{'expected_revision':1,'confirmed':True}),('/profiles',command),('/profiles/trust-profile-x/delete',{'expected_revision':1,'confirmed':True})]:
                response=self.client.post('/api/v1/router-workspace'+path,json=payload,headers={'X-V2-Demo-Action':'router-workspace'});self.assertEqual(response.status_code,403,response.text)
        self.assertEqual(self.client.get('/api/v1/router-workspace/profiles').status_code,403)
        with patch.object(router_center,'snapshot',side_effect=AssertionError('provider dispatched')):
            self.assertEqual(self.client.get('/api/v1/router-center/'+self.allowed+'/pppoe-observations').status_code,403)
        self.assertEqual(self.client.get('/api/v1/router-center/'+self.allowed+'/subscribers?access_type=PPPOE').status_code,200)
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace').status_code,200)
        self.assertEqual(self.client.get('/api/v1/subscriber-observations/'+self.allowed+'/account?source=LOCAL').status_code,403)
    def test_viewer_scope_and_central_admin_regression(self):
        self.user['role_code']='VIEWER'
        self.assertEqual(self.client.get('/api/v1/router-workspace/routers').json()['total'],1)
        self.user.update(role_code='ADMIN',can_manage_users=True)
        self.assertEqual(self.client.get('/api/v1/router-workspace/routers').json()['total'],2)
        self.assertEqual(self.client.get('/api/v1/router-workspace/profiles').status_code,200)

    def test_real_login_me_response_preserves_source_and_refreshes_workspace_grants(self):
        from http.cookies import SimpleCookie
        from app.api.v1 import auth
        from app.core import security
        from app.services.identity import bootstrap
        account=bootstrap()
        account.update(id=self.user['id'],username='fixture-operator',role='OPERATOR',permissions=self.user['permissions'],bootstrap_closed=True,account_origin='LOCAL')
        self.client.app.dependency_overrides.clear()
        self.client.app.include_router(auth.router,prefix='/api/v1')
        with patch.object(security,'find_user',return_value=account):
            response=self.client.post('/api/v1/auth/login',json={'username':'fixture-operator','password':'demo-only'})
            self.assertEqual(response.status_code,200,response.text)
            token=SimpleCookie(response.headers['set-cookie'])['v2_session'].value
            self.addCleanup(security.logout_demo,token)
            headers={'Cookie':'v2_session='+token}
            for payload in (response.json(),self.client.get('/api/v1/auth/me',headers=headers).json()):
                self.assertEqual(payload['router_inventory_source'],'PERSISTENT_WORKSPACE')
                self.assertEqual(payload['role_code'],'OPERATOR')
                self.assertFalse(payload['can_manage_users'])
                self.assertTrue(payload['permissions'][self.allowed]['can_view'])
                self.assertNotIn('password_hash',payload)
            self.assertEqual(self.client.get('/api/v1/router-workspace/routers',headers=headers).json()['total'],1)
            self.assertEqual(self.client.get('/api/v1/router-workspace/routers/'+self.hidden,headers=headers).status_code,404)
            account['permissions'][self.allowed]['can_view']=False
            account['revision']+=1
            refreshed=self.client.get('/api/v1/auth/me',headers=headers).json()
            self.assertEqual(refreshed['router_inventory_source'],'PERSISTENT_WORKSPACE')
            self.assertNotIn(self.allowed,refreshed['permissions'])
            self.assertEqual(refreshed['revision'],account['revision'])
            self.assertEqual(self.client.get('/api/v1/router-workspace/routers',headers=headers).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/router-workspace/routers/'+self.allowed,headers=headers).status_code,404)
            account['permissions'][self.allowed]['can_view']=True
            account['revision']+=1
            refreshed=self.client.get('/api/v1/auth/me',headers=headers).json()
            self.assertTrue(refreshed['permissions'][self.allowed]['can_view'])
            self.assertEqual(self.client.get('/api/v1/dashboard/summary',headers=headers).json()['summary']['router_count'],1)
            self.assertEqual(self.client.get('/api/v1/router-workspace/profiles',headers=headers).status_code,403)
