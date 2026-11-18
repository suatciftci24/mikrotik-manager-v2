"""Scoped synthetic PPPoE lifecycle over ASGI + disposable SQLite, no external IO."""
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from sqlalchemy import select,func,event
from sqlalchemy.exc import SQLAlchemyError
from app.models.router_workspace import RouterWorkspaceRecord as Router
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as Audit
from app.services.subscriber_center import SubscriberWorkspace
from app.services.subscriber_operations import SubscriberOperationsService
from backend.tests.test_workspace_operator_access import OperatorAccess

class PppoeWorkspace(TestCase):
    def setUp(self):
        OperatorAccess.setUp(self)
        self.allowed='demo-managed-router-'+str(uuid4());self.hidden='demo-managed-router-'+str(uuid4())
        with self.sessions.begin() as session:
            for id in (self.allowed,self.hidden):session.add(Router(id=id,kind='DEMO_ROUTER',revision=1,fields={'name':'V26 Test Router' if id==self.allowed else 'Foreign','management_address':'192.0.2.10','model':'Synthetic','site':''}))
        self.accounts=SubscriberWorkspace(self.sessions,lambda session:None)
        self.ops=SubscriberOperationsService(self.sessions,lambda session:None)
        for target,value in [('app.services.subscriber_center.workspace',self.accounts),('app.api.v1.subscriber_center.workspace',self.accounts),('app.api.v1.subscriber_center.operations',self.ops)]:
            p=patch(target,value);p.start();self.addCleanup(p.stop)
        self.user['permissions']={self.allowed:{'can_view':True,'can_manage_pppoe':True},self.hidden:{'can_view':False,'can_manage_pppoe':True}}
        names_patch=patch('app.services.identity.audit_actor_usernames',return_value={})
        self.names=names_patch.start();self.addCleanup(names_patch.stop)
        self.headers={'X-V2-Demo-Action':'subscriber-workspace'}
    def command(self,router=None,**fields):
        return dict(request_id=str(uuid4()),fields=dict(customer_name='Synthetic Subscriber',username='fixture.'+uuid4().hex,router_id=router or self.allowed,access_type='PPPOE',source='LOCAL',plan='Plan 100',status='ACTIVE',started_on='2026-01-01',expires_on='2030-01-01',**fields),expected_revision=0,confirmed=True)
    def post(self,path,payload):return self.client.post('/api/v1'+path,json=payload,headers=self.headers)
    def create(self,command=None):
        payload=command or self.command();response=self.post('/subscriber-workspace',payload);self.assertEqual(response.status_code,200,response.text);return payload,response.json()
    def counts(self):
        with self.sessions() as s:return (s.scalar(select(func.count()).select_from(Account)),s.scalar(select(func.count()).select_from(Audit)))
    def operation(self,item,kind,value):
        return dict(request_id=str(uuid4()),item_id=item['id'],expected_revision=item['revision'],expected_router_id=item['router_id'],expected_source=item['source'],operation=kind,value=value,confirmed=True)
    def test_operator_create_persist_edit_status_plan_renew_replay_and_scoped_audit(self):
        self.assertEqual(self.client.get('/api/v1/dashboard/summary').json()['summary']['subscribers_total'],0)
        payload,item=self.create();self.assertEqual(self.counts(),(1,1))
        self.assertEqual(self.post('/subscriber-workspace',payload).json(),item);self.assertEqual(self.counts(),(1,1))
        detail=self.client.get('/api/v1/subscriber-center/'+item['id']).json();self.assertTrue(detail['item']['can_manage']);self.assertEqual(detail['item']['started_on'],'2026-01-01')
        fields={**payload['fields'],'customer_name':'Edited Subscriber'}
        update={**payload,'request_id':str(uuid4()),'fields':fields,'expected_revision':1}
        self.assertEqual(self.post('/subscriber-workspace/'+item['id'],update).status_code,200)
        item=self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item']
        for kind,value in [('PLAN','Plan 200'),('STATUS','PAUSED')]:
            command=self.operation(item,kind,value);response=self.post('/subscriber-workspace/management/execute',{'entries':[command]});self.assertEqual(response.status_code,200,response.text);self.assertTrue(response.json()['results'][0]['success'])
            self.assertEqual(self.post('/subscriber-workspace/management/execute',{'entries':[command]}).json(),response.json())
            item=self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item']
        self.assertEqual(item['expires_on'],'2030-01-01')
        renewal=dict(request_id=str(uuid4()),expected_revision=item['revision'],expected_source='LOCAL',expected_expires_on=item['expires_on'],expires_on='2030-01-31',days=30,confirmed=True)
        response=self.post('/subscriber-workspace/'+item['id']+'/renew',renewal);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.post('/subscriber-workspace/'+item['id']+'/renew',renewal).json(),response.json())
        receipt=self.client.get('/api/v1/subscriber-workspace/renewals/requests/'+renewal['request_id']);self.assertEqual(receipt.json()['status'],'SUCCESS')
        self.assertEqual(self.counts(),(1,5))
        reloaded=SubscriberWorkspace(self.sessions,lambda session:None).detail(item['id'],user=self.user);self.assertEqual(reloaded.item.plan,'Plan 200');self.assertEqual(reloaded.item.expires_on.isoformat(),'2030-01-31');self.assertEqual(len(reloaded.history),5)
        history=self.client.get('/api/v1/subscriber-workspace/management/history').json();self.assertEqual(history['total'],5)
        options=self.client.get('/api/v1/subscriber-workspace/options');self.assertEqual(options.status_code,200,options.text);self.assertEqual(options.json()['plans'],['Plan 200'])
        summary=self.client.get('/api/v1/dashboard/summary').json()['summary'];listing=self.client.get('/api/v1/subscriber-workspace').json();self.assertEqual(summary['subscribers_total'],listing['total']);self.assertEqual(summary['local_accounts'],1)
    def test_readonly_viewer_foreign_router_and_forged_expected_binding_cannot_write(self):
        payload,item=self.create()
        before=self.counts()
        hotspot=self.command();hotspot['fields']['access_type']='HOTSPOT'
        self.assertEqual(self.post('/subscriber-workspace',hotspot).status_code,403)
        forged=self.operation(item,'PLAN','Forged')
        forged['expected_router_id']=self.hidden
        self.assertEqual(self.post('/subscriber-workspace/management/execute',{'entries':[forged]}).status_code,404)
        self.assertEqual(self.counts(),before)
        self.user['permissions'][self.allowed]['can_manage_pppoe']=False
        self.assertFalse(self.client.get('/api/v1/subscriber-workspace').json()['items'][0]['can_manage'])
        self.assertEqual(self.post('/subscriber-workspace',self.command()).status_code,403)
        operation=self.operation(item,'PLAN','Forbidden')
        self.assertEqual(self.post('/subscriber-workspace/management/execute',{'entries':[operation]}).status_code,403)
        self.assertEqual(self.post('/subscriber-workspace/'+item['id'],{**payload,'request_id':str(uuid4()),'expected_revision':1}).status_code,403)
        self.user['role_code']='VIEWER';self.user['permissions'][self.allowed]['can_manage_pppoe']=True
        self.assertEqual(self.post('/subscriber-workspace',self.command()).status_code,403)
        self.user['role_code']='OPERATOR'
        self.assertEqual(self.post('/subscriber-workspace',self.command(self.hidden)).status_code,404)
        self.user['permissions']={self.hidden:{'can_view':True,'can_manage_pppoe':True}}
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace').json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/subscriber-center/'+item['id']).status_code,404)
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace/management/history').json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace/options').json()['plans'],[])
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace/requests/'+payload['request_id']).status_code,404)
        operation['expected_router_id']=self.hidden
        self.assertEqual(self.post('/subscriber-workspace/management/execute',{'entries':[operation]}).status_code,404)
        self.assertEqual(self.counts(),before)
    def test_date_validation_legacy_field_preservation_and_audit_failure_rollback(self):
        invalid=self.command();invalid['fields']['expires_on']='2025-01-01'
        self.assertEqual(self.post('/subscriber-workspace',invalid).status_code,422);self.assertEqual(self.counts(),(0,0))
        payload,item=self.create();before=self.counts()
        fields={**payload['fields'],'plan':'Plan Legacy Client'};fields.pop('started_on')
        update={**payload,'request_id':str(uuid4()),'fields':fields,'expected_revision':1}
        self.assertEqual(self.post('/subscriber-workspace/'+item['id'],update).json()['started_on'],'2026-01-01')
        item=self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item'];before=self.counts()
        expires=self.operation(item,'EXPIRE','2025-01-01');result=self.post('/subscriber-workspace/management/execute',{'entries':[expires]}).json()['results'][0];self.assertFalse(result['success'])
        self.assertEqual(self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item']['expires_on'],item['expires_on'])
        before=self.counts()
        def fail(mapper,connection,target):raise SQLAlchemyError('synthetic audit failure')
        event.listen(Audit,'before_insert',fail)
        try:
            bad=self.command();self.assertEqual(self.post('/subscriber-workspace',bad).status_code,503)
            edit={**update,'request_id':str(uuid4()),'expected_revision':item['revision'],'fields':{**fields,'plan':'Rollback'}}
            self.assertEqual(self.post('/subscriber-workspace/'+item['id'],edit).status_code,503)
            command=self.operation(item,'PLAN','Audit Rollback')
            failed=self.post('/subscriber-workspace/management/execute',{'entries':[command]}).json()['results'][0]
            self.assertFalse(failed['success']);self.assertFalse(failed['recorded'])
        finally:event.remove(Audit,'before_insert',fail)
        self.assertEqual(self.counts(),before)
        self.assertEqual(self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item']['plan'],item['plan'])
        self.assertEqual(self.post('/subscriber-workspace',bad).status_code,200)
    def test_bulk_preflight_and_router_reassignment_are_not_operator_escalations(self):
        payload,item=self.create();before=self.counts()
        command=self.operation(item,'ROUTER',self.hidden)
        self.assertEqual(self.post('/subscriber-workspace/management/execute',{'entries':[command]}).status_code,403)
        # A forbidden second member must not leave the authorized first member changed.
        other=self.command(self.hidden);other['fields']['plan']='Foreign Profile'
        self.user.update(role_code='ADMIN',can_manage_users=True)
        _,foreign=self.create(other)
        self.user.update(role_code='OPERATOR',can_manage_users=False)
        before=self.counts()
        listed=self.client.get('/api/v1/subscriber-workspace?page_size=1').json()
        self.assertEqual(listed['total'],1);self.assertEqual(listed['items'][0]['id'],item['id'])
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace?page=2&page_size=1').json()['items'],[])
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace?query='+foreign['username']).json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace?router_id='+self.hidden).json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace/options').json()['plans'],['Plan 100'])
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace/management/history').json()['total'],1)
        commands=[self.operation(item,'STATUS','PAUSED'),self.operation(foreign,'STATUS','PAUSED')]
        self.assertEqual(self.post('/subscriber-workspace/management/execute',{'entries':commands}).status_code,404)
        self.assertEqual(self.counts(),before)
        self.assertEqual(self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item']['status'],'ACTIVE')
    def test_moved_account_does_not_expose_foreign_router_audit_or_old_receipts(self):
        payload,item=self.create()
        renewal=dict(request_id=str(uuid4()),expected_revision=1,expected_source='LOCAL',expected_expires_on='2030-01-01',expires_on='2030-01-31',days=30,confirmed=True)
        item=self.post('/subscriber-workspace/'+item['id']+'/renew',renewal).json()
        plan=self.operation(item,'PLAN','Plan 300')
        self.assertTrue(self.post('/subscriber-workspace/management/execute',{'entries':[plan]}).json()['results'][0]['success'])
        item=self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item']
        self.user.update(role_code='ADMIN',can_manage_users=True)
        move=self.operation(item,'ROUTER',self.hidden)
        self.assertTrue(self.post('/subscriber-workspace/management/execute',{'entries':[move]}).json()['results'][0]['success'])
        self.user.update(role_code='OPERATOR',can_manage_users=False,permissions={self.hidden:{'can_view':True,'can_manage_pppoe':True}})
        detail=self.client.get('/api/v1/subscriber-center/'+item['id']).json()
        self.assertEqual(detail['history'],[])
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace/management/history').json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace/renewals/requests/'+renewal['request_id']).status_code,404)
        self.assertEqual(self.post('/subscriber-workspace/'+item['id']+'/renew',renewal).status_code,404)
        self.assertEqual(self.post('/subscriber-workspace/management/execute',{'entries':[plan]}).status_code,404)
        self.assertEqual(self.client.get('/api/v1/subscriber-workspace/management/requests/'+plan['request_id']).status_code,404)

    def test_pre_started_on_receipts_and_uuid_replay_remain_compatible(self):
        import hashlib,json
        payload=self.command();payload['fields'].pop('started_on')
        _,item=self.create(payload)
        with self.sessions.begin() as session:
            account=session.get(Account,item['id']);fields=dict(account.fields);fields.pop('started_on');account.fields=fields
            audit=session.get(Audit,payload['request_id']);changes=dict(audit.changes);saved=dict(changes['_save']);response=dict(saved['response']);response.pop('started_on');response.pop('can_manage');saved['response']=response
            saved['fingerprint']=hashlib.sha256(json.dumps([self.user['id'],None,payload],sort_keys=True,separators=(',',':')).encode()).hexdigest()
            changes['_save']=saved;audit.changes=changes
        before=self.counts()
        replay=self.post('/subscriber-workspace',payload);self.assertEqual(replay.status_code,200,replay.text)
        self.assertEqual(replay.json()['id'],item['id']);self.assertEqual(self.counts(),before)
        receipt=self.client.get('/api/v1/subscriber-workspace/requests/'+payload['request_id']);self.assertEqual(receipt.json()['status'],'SUCCESS')

    def test_report_history_requires_report_grant_and_scopes_before_pagination(self):
        _,item=self.create()
        self.user['permissions'][self.hidden]={'can_view':True,'can_manage_pppoe':True}
        self.create(self.command(router=self.hidden))
        path='/api/v1/subscriber-workspace/management/history?report=true&page_size=1'
        self.assertEqual(self.client.get(path).status_code,403)
        self.user['permissions'][self.allowed]['can_view_reports']=True
        result=self.client.get(path)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['total'],1)
        self.assertEqual(result.json()['items'][0]['item_id'],item['id'])
        self.user['permissions'][self.allowed]['can_view']=False
        self.assertEqual(self.client.get(path).status_code,403)

    def test_daily_report_filters_counts_and_actor_names_use_report_scope(self):
        _,item=self.create()
        self.user['permissions'][self.hidden]={'can_view':True,'can_manage_pppoe':True}
        _,foreign=self.create(self.command(router=self.hidden))
        path='/api/v1/subscriber-workspace/management/history'
        def report(params):
            return self.client.get(path+'?'+urlencode(params))
        execute_path='/subscriber-workspace/management/execute'
        success=self.operation(item,'STATUS','PAUSED')
        self.assertTrue(self.post(execute_path,{'entries':[success]}).json()['results'][0]['success'])
        self.assertTrue(self.post(execute_path,{'entries':[self.operation(foreign,'STATUS','PAUSED')]}).json()['results'][0]['success'])
        conflict=self.operation(item,'STATUS','ACTIVE')
        self.assertFalse(self.post(execute_path,{'entries':[conflict]}).json()['results'][0]['success'])
        self.assertEqual(report({'daily':'true'}).status_code,403)
        self.user['permissions'][self.allowed]['can_view_reports']=True
        self.names.return_value={self.user['id']:'operator.fixture'}
        day=datetime.now(ZoneInfo('Europe/Istanbul')).date()
        filters={'daily':'true','start':day.isoformat(),'end':day.isoformat(),'actor_id':self.user['id'],'operation':'STATUS'}
        response=report({**filters,'result':'SUCCESS','page_size':1})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['counts'],{'success':1,'failed':1,'skipped':None})
        self.assertEqual(data['total'],1)
        row=data['items'][0]
        self.assertEqual(row['item_id'],item['id'])
        self.assertEqual(row['subscriber_username'],item['username'])
        self.assertEqual(row['actor_username'],'operator.fixture')
        self.assertEqual(row['previous'],{'status':'ACTIVE'})
        self.assertEqual(row['values'],{'status':'PAUSED'})
        self.names.assert_called_with([self.user['id']])
        for overrides in ({'actor_id':'other'},{'operation':'PLAN'},
                          {'start':(day-timedelta(days=1)).isoformat(),'end':(day-timedelta(days=1)).isoformat()}):
            self.assertEqual(report({**filters,**overrides}).json()['total'],0)
        skipped=report({**filters,'result':'SKIPPED'}).json()
        self.assertEqual(skipped['items'],[])
        self.assertIsNone(skipped['counts']['skipped'])
        self.assertEqual(report({**filters,'end':'invalid'}).status_code,422)

    def test_actor_names_enrich_only_authorized_history_and_preserve_raw_audit(self):
        _,item=self.create()
        self.names.return_value={self.user['id']:'existing.operator'}
        path='/api/v1/subscriber-center/'+item['id']
        response=self.client.get(path)
        self.assertEqual(response.status_code,200,response.text)
        history=response.json()['history']
        self.assertEqual(history[0]['actor_username'],'existing.operator')
        self.assertEqual(history[0]['actor_id'],self.user['id'])
        self.names.assert_called_once_with({self.user['id']})
        self.assertNotIn('actor_username',self.accounts.detail(item['id']).history[0].model_dump(exclude_none=True))
        self.names.reset_mock()
        self.user['permissions'][self.allowed]['can_view']=False
        self.assertEqual(self.client.get(path).status_code,404)
        self.names.assert_not_called()
        self.user['permissions'][self.allowed]['can_view']=True
        from app.services.demo_subscriptions import DemoStorageUnavailable
        self.names.side_effect=DemoStorageUnavailable()
        fallback=self.client.get(path)
        self.assertEqual(fallback.status_code,200,fallback.text)
        self.assertIsNone(fallback.json()['history'][0]['actor_username'])
        self.assertEqual(fallback.json()['history'][0]['actor_id'],history[0]['actor_id'])
