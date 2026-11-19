"""Scoped synthetic PPPoE lifecycle over ASGI + disposable SQLite, no external IO."""
from concurrent.futures import ThreadPoolExecutor
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
from app.schemas.subscriber_management_center import UndoOperations
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
        applied=self.post(execute_path,{'entries':[success]}).json()['results'][0]
        self.assertTrue(applied['success'])
        skip=self.operation({**item,'revision':applied['revision'],'status':'PAUSED'},'STATUS','PAUSED')
        foreign_change=self.operation(foreign,'STATUS','PAUSED')
        batch=self.post(execute_path,{'entries':[skip,foreign_change]}).json()['results']
        group_id=batch[0]['group_id']
        self.assertEqual(batch[1]['group_id'],group_id)
        self.assertTrue(batch[0]['skipped'])
        self.assertTrue(batch[1]['success'])
        conflict=self.operation(item,'STATUS','ACTIVE')
        self.assertFalse(self.post(execute_path,{'entries':[conflict]}).json()['results'][0]['success'])
        self.assertEqual(report({'daily':'true'}).status_code,403)
        self.names.return_value={self.user['id']:'operator.fixture'}
        central=report({'include_skipped':'true','result':'SKIPPED'}).json()
        self.assertEqual(central['total'],1)
        self.assertEqual(central['items'][0]['group_id'],group_id)
        self.assertEqual(central['items'][0]['request_id'],skip['request_id'])
        self.assertEqual(central['items'][0]['actor_username'],'operator.fixture')
        self.assertEqual(central['items'][0]['occurred_at'],batch[0]['occurred_at'])
        self.user['permissions'][self.allowed]['can_view']=False
        self.assertEqual(report({'include_skipped':'true','result':'SKIPPED'}).json()['total'],0)
        self.user['permissions'][self.allowed]['can_view']=True
        self.assertEqual(report({'include_skipped':'true','operation':'CREATE'}).json()['total'],2)
        self.user['permissions'][self.hidden]['can_view']=False
        self.assertEqual(report({'include_skipped':'true','operation':'CREATE'}).json()['total'],1)
        self.user['permissions'][self.hidden]['can_view']=True
        self.assertEqual(report({'operation':'STATUS'}).json()['total'],3)
        self.user['permissions'][self.allowed]['can_view_reports']=True
        day=datetime.now(ZoneInfo('Europe/Istanbul')).date()
        filters={'daily':'true','start':day.isoformat(),'end':day.isoformat(),'actor_id':self.user['id'],'operation':'STATUS'}
        response=report({**filters,'result':'SUCCESS','page_size':1})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['counts'],{'success':1,'failed':1,'skipped':1})
        self.assertEqual(data['total'],1)
        row=data['items'][0]
        self.assertEqual(row['item_id'],item['id'])
        self.assertEqual(row['execution_type'],'SINGLE')
        self.assertIsNone(row['group_id'])
        self.assertEqual(row['subscriber_username'],item['username'])
        self.assertEqual(row['actor_username'],'operator.fixture')
        self.assertEqual(row['previous'],{'status':'ACTIVE'})
        self.assertEqual(row['values'],{'status':'PAUSED'})
        self.names.assert_called_with([self.user['id']])
        for overrides in ({'actor_id':'other'},{'operation':'PLAN'},
                          {'start':(day-timedelta(days=1)).isoformat(),'end':(day-timedelta(days=1)).isoformat()}):
            self.assertEqual(report({**filters,**overrides}).json()['total'],0)
        skipped=report({**filters,'result':'SKIPPED'}).json()
        self.assertEqual([row['request_id'] for row in skipped['items']],[skip['request_id']])
        self.assertEqual(skipped['groups'],[dict(group_id=group_id,total=1,success=0,failed=0,skipped=1)])
        self.assertEqual(report({**filters,'execution_type':'BULK','group_id':group_id}).json()['total'],1)
        self.assertEqual(report({**filters,'execution_type':'SINGLE'}).json()['total'],2)
        recovery='/api/v1'+execute_path.replace('/execute','/requests/')+skip['request_id']
        self.assertEqual(self.client.get(recovery).json()['status'],'SKIPPED')
        self.user['permissions'][self.allowed]['can_view']=False
        self.assertEqual(self.client.get(recovery).status_code,404)
        self.user['permissions'][self.allowed]['can_view']=True
        self.assertEqual(report({**filters,'end':'invalid'}).status_code,422)
        with self.sessions.begin() as session:
            event=session.get(Audit,success['request_id'])
            changes=event.changes
            management=changes['_management']
            legacy={key:value for key,value in management['receipt'].items()
                    if key not in ('execution_type','group_id')}
            event.changes={**changes,'_management':{**management,'receipt':legacy}}
        legacy_report=report({**filters,'execution_type':'UNKNOWN'}).json()
        self.assertEqual(legacy_report['total'],1)
        self.assertIsNone(legacy_report['items'][0]['execution_type'])
        self.assertIsNone(legacy_report['items'][0]['group_id'])

    def test_group_and_undo_preview_are_readonly_and_scoped(self):
        created, item = self.create()
        _, skipped_item = self.create()
        _, rejected_item = self.create()
        self.user['permissions'][self.hidden]['can_view'] = True
        _, hidden_item = self.create(self.command(router=self.hidden))
        execute_path = '/subscriber-workspace/management/execute'
        self.assertTrue(self.post(execute_path, {'entries':[self.operation(skipped_item,'STATUS','PAUSED')]}).json()['results'][0]['success'])
        skipped_item = self.client.get('/api/v1/subscriber-center/'+skipped_item['id']).json()['item']
        rejected = {**self.operation(rejected_item, 'STATUS', 'PAUSED'), 'expected_revision':99}
        commands = [self.operation(row,'STATUS','PAUSED') for row in (item,skipped_item,hidden_item)]
        response = self.post(execute_path, {'entries':[*commands,rejected]})
        self.assertEqual(response.status_code, 200, response.text)
        applied, skipped, hidden, failed = response.json()['results']
        self.user['permissions'][self.hidden]['can_view'] = False
        history = '/api/v1/subscriber-workspace/management/history'
        def preview(receipt):
            return self.client.get(f"{history}/{receipt['request_id']}/undo-preview")

        engine = self.sessions.kw['bind']
        statements = []
        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.split()[0].upper())

        event.listen(engine, 'before_cursor_execute', capture)
        try:
            group = self.client.get(f"{history}?include_skipped=true&group_id={applied['group_id']}").json()
            self.assertEqual(group['total'], 3)
            self.assertEqual({row['request_id'] for row in group['items']}, {r['request_id'] for r in (applied, skipped, failed)})
            self.assertTrue(all(row['subscriber_name']=='Synthetic Subscriber' for row in group['items']))
            result = preview(applied).json()
            self.assertEqual(result['status'], 'ELIGIBLE')
            self.assertEqual(result['changes'], [dict(field='status', previous='ACTIVE', applied='PAUSED', current='PAUSED')])
            for receipt, reason in ((skipped, 'atlandı'), (failed, 'reddedildi'), (created, 'kanıtı')):
                data = preview(receipt).json()
                self.assertEqual(data['status'], 'INELIGIBLE')
                self.assertIn(reason, data['reason'])
            self.assertEqual(preview(hidden).status_code, 404)
            self.user['permissions'][self.allowed]['can_manage_pppoe'] = False
            self.assertIn('yetkiniz', preview(applied).json()['reason'])
            self.user['permissions'][self.allowed]['can_manage_pppoe'] = True
        finally:
            event.remove(engine, 'before_cursor_execute', capture)
        self.assertEqual(set(statements), {'SELECT'})

        current = self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item']
        edit = self.post(execute_path, {'entries':[self.operation(current,'EDIT','New synthetic name')]})
        self.assertTrue(edit.json()['results'][0]['success'])
        data = preview(applied).json()
        self.assertEqual(data['status'], 'CONFLICT')
        self.assertGreater(data['current_revision'], data['audit_revision'])
        self.assertEqual(data['changes'][0]['current'], 'PAUSED')
        self.assertEqual(self.client.post(f"{history}/{applied['request_id']}/undo-preview",json={}).status_code,405)

    def test_undo_preview_distinguishes_saved_null_expiry_from_missing_audit_value(self):
        _, item = self.create()
        path = '/subscriber-workspace/management/execute'
        cleared = self.post(path, {'entries':[self.operation(item,'EXPIRE',None)]}).json()['results'][0]
        self.assertTrue(cleared['success'])
        current = self.client.get('/api/v1/subscriber-center/'+item['id']).json()['item']
        applied = self.post(path, {'entries':[self.operation(current,'EXPIRE','2030-02-01')]}).json()['results'][0]
        self.assertTrue(applied['success'])
        preview = f"/api/v1/subscriber-workspace/management/history/{applied['request_id']}/undo-preview"
        data = self.client.get(preview).json()
        self.assertEqual(data['status'], 'ELIGIBLE')
        self.assertEqual(data['changes'], [dict(field='expires_on',previous=None,applied='2030-02-01',current='2030-02-01')])
        with self.sessions.begin() as session:
            stored = session.get(Audit, applied['request_id'])
            stored.changes = {**stored.changes, 'expires_on':{'new':'2030-02-01'}}
        data = self.client.get(preview).json()
        self.assertEqual(data['status'], 'INELIGIBLE')
        self.assertEqual(data['changes'], [])

    def undo_command(self, receipt):
        preview = self.ops.undo_preview(receipt['request_id'], self.user)
        self.assertEqual(preview['status'], 'ELIGIBLE')
        change, = preview['changes']
        return dict(request_id=str(uuid4()), source_request_id=receipt['request_id'], source_group_id=preview['source_group_id'],
                    item_id=receipt['item_id'], expected_revision=preview['current_revision'],
                    field=change['field'], previous=change['previous'], applied=change['applied'])

    def test_undo_single_audit_replay_and_isolation(self):
        _, account = self.create()
        source = self.post('/subscriber-workspace/management/execute',
                           {'entries':[self.operation(account, 'STATUS', 'PAUSED')]}).json()['results'][0]
        entry = self.undo_command(source)
        path = '/subscriber-workspace/management/undo'
        body = {'confirmed':True, 'entries':[entry]}
        with patch.dict('os.environ', {'V2_V26_RUNTIME_LAYOUT':'vds-next'}):
            self.assertEqual(self.post(path, body).status_code, 403)
        self.assertEqual(self.post(path, {**body, 'confirmed':1}).status_code, 422)
        self.user['permissions'][self.allowed]['can_manage_pppoe'] = False
        self.assertEqual(self.post(path, body).status_code, 403)
        self.user['permissions'][self.allowed]['can_manage_pppoe'] = True
        baseline = self.counts()
        response = self.post(path, body)
        self.assertEqual(response.status_code, 200, response.text)
        receipt, = response.json()['results']
        self.assertEqual(receipt['operation'], 'UNDO')
        self.assertTrue(receipt['success'])
        self.assertEqual(receipt['source_request_id'], source['request_id'])
        self.assertIsNone(receipt['source_group_id'])
        self.assertEqual(receipt['actor_id'], self.user['id'])
        self.assertEqual(receipt['previous'], {'status':'PAUSED'})
        self.assertEqual(receipt['values'], {'status':'ACTIVE'})
        self.assertEqual(self.post(path, body).json(), response.json())
        self.assertEqual(self.post(path, {**body, 'entries':[{**entry,'previous':'PAUSED'}]}).status_code, 409)
        self.assertEqual(self.counts(), (baseline[0],baseline[1]+1))
        history = '/api/v1/subscriber-workspace/management/history?include_skipped=true&request_id='
        self.assertEqual(self.client.get(history+receipt['request_id']).json()['total'], 1)
        recovered = self.client.get('/api/v1/subscriber-workspace/management/requests/'+entry['request_id']).json()
        self.assertEqual(recovered['status'], 'SUCCESS')
        self.assertEqual(recovered['response'], receipt)
        preview = self.client.get('/api/v1/subscriber-workspace/management/history/'+source['request_id']+'/undo-preview').json()
        self.assertEqual((preview['status'],preview['undo_request_id']), ('UNDONE',receipt['request_id']))
        second = self.post(path, {**body, 'entries':[{**entry,'request_id':str(uuid4())}]}).json()['results'][0]
        self.assertFalse(second['success'])
        self.assertIn('başarılı geri alma kaydı', second['error'])
        self.assertEqual(self.post(path, body).json(), response.json())
        found = self.client.get(history+source['request_id']+'&undo_status=UNDONE&page_size=1').json()
        self.assertEqual(found['total'],1)
        self.assertEqual(found['items'][0]['undo_request_id'],receipt['request_id'])
        current = self.client.get('/api/v1/subscriber-center/'+account['id']).json()['item']
        self.assertEqual((current['status'], current['revision']), ('ACTIVE', account['revision']+2))

    def test_group_undo_rejects_stale_member_and_rolls_back_storage_failure(self):
        _, first = self.create()
        _, second = self.create()
        batch = self.post('/subscriber-workspace/management/execute',
                          {'entries':[self.operation(row,'STATUS','PAUSED') for row in (first,second)]}).json()['results']
        entries = [self.undo_command(receipt) for receipt in batch]
        preview = self.client.get('/api/v1/subscriber-workspace/management/history/groups/'+batch[0]['group_id']+'/undo-preview')
        self.assertEqual({row['request_id'] for row in preview.json()['items']}, {r['request_id'] for r in batch})
        baseline = self.counts()
        original = self.ops.audit
        def storage_failure(session, command, actor, changes, receipt, source):
            if receipt['item_id'] == second['id']:
                raise SQLAlchemyError('test storage failure')
            original(session, command, actor, changes, receipt, source)
            session.flush()

        path = '/subscriber-workspace/management/undo'
        body = {'confirmed':True,'entries':entries}
        with patch.object(self.ops, 'audit', side_effect=storage_failure):
            self.assertEqual(self.post(path, body).status_code, 503)
        self.assertEqual(self.counts(), baseline)
        for row in (first,second):
            current = self.client.get('/api/v1/subscriber-center/'+row['id']).json()['item']
            self.assertEqual((current['status'],current['revision']), ('PAUSED',2))
        current = self.client.get('/api/v1/subscriber-center/'+second['id']).json()['item']
        self.post('/subscriber-workspace/management/execute', {'entries':[self.operation(current,'EDIT','After preview')]})
        results = self.post(path,body).json()['results']
        self.assertEqual([result['success'] for result in results], [False,False])
        self.assertIn('başka bir kayıt', results[0]['error'])
        self.assertIn('revizyonu değişti', results[1]['error'])
        self.assertEqual({r['source_group_id'] for r in results}, {batch[0]['group_id']})
        self.assertEqual(len({r['group_id'] for r in results}), 1)
        self.assertEqual(self.post(path,body).json()['results'], results)
        self.assertEqual(self.client.get('/api/v1/subscriber-center/'+first['id']).json()['item']['status'],'PAUSED')

    def test_group_undo_requires_every_original_member_and_blocks_skips(self):
        _, first = self.create()
        _, second = self.create()
        execute = '/subscriber-workspace/management/execute'
        self.post(execute, {'entries':[self.operation(second,'STATUS','PAUSED')]})
        second = self.client.get('/api/v1/subscriber-center/'+second['id']).json()['item']
        changed, skipped = self.post(execute, {'entries':[self.operation(row,'STATUS','PAUSED')
                                                         for row in (first,second)]}).json()['results']
        group = '/api/v1/subscriber-workspace/management/history/groups/'+changed['group_id']+'/undo-preview'
        preview = self.client.get(group).json()
        self.assertFalse(preview['can_execute'])
        self.assertEqual({row['status'] for row in preview['items']},{'ELIGIBLE','INELIGIBLE'})
        self.assertTrue(all(row['actor_id']==self.user['id'] and row['occurred_at'] for row in preview['items']))
        first_entry = self.undo_command(changed)
        second_entry = {**first_entry, 'request_id':str(uuid4()),'source_request_id':skipped['request_id'],
                        'item_id':skipped['item_id'],'expected_revision':skipped['revision']}
        undo = '/subscriber-workspace/management/undo'
        baseline = self.counts()
        incomplete = self.post(undo, {'confirmed':True,'entries':[first_entry]})
        self.assertEqual(incomplete.status_code,409)
        self.assertEqual(self.counts(),baseline)
        complete = self.post(undo, {'confirmed':True,'entries':[first_entry,second_entry]}).json()['results']
        self.assertEqual([r['success'] for r in complete],[False,False])
        self.assertIn('atlandı',complete[1]['error'])
        current = self.client.get('/api/v1/subscriber-center/'+first['id']).json()['item']
        self.assertEqual((current['status'],current['revision']),('PAUSED',changed['revision']))

    def test_undo_rejects_inconsistent_source_group_audit_and_preserves_legacy_single(self):
        _, first = self.create()
        _, second = self.create()
        execute = '/subscriber-workspace/management/execute'
        source = self.post(execute, {'entries':[self.operation(account,'STATUS','PAUSED')
                                                for account in (first,second)]}).json()['results'][0]
        entry = self.undo_command(source)
        with self.sessions.begin() as session:
            audit = session.get(Audit, source['request_id'])
            management = audit.changes['_management']
            receipt = {key:value for key,value in management['receipt'].items() if key != 'group_id'}
            audit.changes = {**audit.changes,'_management':{**management,'receipt':receipt}}

        history = '/api/v1/subscriber-workspace/management/history/'
        preview = self.client.get(history+source['request_id']+'/undo-preview').json()
        self.assertEqual(preview['status'],'INELIGIBLE')
        self.assertIn('grup bilgisi',preview['reason'])
        path = '/subscriber-workspace/management/undo'
        baseline = self.counts()
        denied = self.post(path, {'confirmed':True,'entries':[{**entry,'source_group_id':None}]})
        self.assertEqual(denied.status_code,409)
        self.assertEqual(self.counts(),baseline)
        current = self.client.get('/api/v1/subscriber-center/'+first['id']).json()['item']
        self.assertEqual((current['status'],current['revision']),('PAUSED',2))

        single = self.post(execute, {'entries':[self.operation(current,'STATUS','ACTIVE')]}).json()['results'][0]
        with self.sessions.begin() as session:
            audit = session.get(Audit, single['request_id'])
            management = audit.changes['_management']
            receipt = {key:value for key,value in management['receipt'].items() if key not in ('group_id','execution_type')}
            audit.changes = {**audit.changes,'_management':{**management,'receipt':receipt}}
        legacy_command = self.undo_command(single)
        self.assertTrue(self.post(path, {'confirmed':True,'entries':[legacy_command]}).json()['results'][0]['success'])

    def test_undo_rechecks_current_value_and_source_account(self):
        _, first = self.create()
        _, other = self.create()
        source = self.post('/subscriber-workspace/management/execute',
                           {'entries':[self.operation(first,'STATUS','PAUSED')]}).json()['results'][0]
        entry = self.undo_command(source)
        path = '/subscriber-workspace/management/undo'
        baseline = self.counts()
        wrong_account = self.post(path, {'confirmed':True,'entries':[{**entry,'item_id':other['id']}]})
        self.assertEqual(wrong_account.status_code,409)
        self.assertEqual(self.counts(),baseline)
        # Simulate a changed value without an accompanying revision in the disposable store.
        with self.sessions.begin() as session:
            account = session.get(Account,first['id'])
            account.fields = {**account.fields,'status':'ACTIVE'}
        result = self.post(path, {'confirmed':True,'entries':[entry]}).json()['results'][0]
        self.assertFalse(result['success'])
        self.assertIn('Güncel değer',result['error'])
        self.assertEqual(result['revision'],source['revision'])
        self.assertEqual(result['values'],{})

    def test_undo_history_filter_is_applied_before_pagination(self):
        _, first = self.create()
        _, second = self.create()
        execute = '/subscriber-workspace/management/execute'
        source = [self.post(execute, {'entries':[self.operation(account,'STATUS','PAUSED')]}).json()['results'][0]
                  for account in (first,second)]
        # Changing the second account leaves the first eligible, regardless of history order.
        latest = self.client.get('/api/v1/subscriber-center/'+second['id']).json()['item']
        self.post(execute, {'entries':[self.operation(latest,'EDIT','Changed after status')]})
        path = '/api/v1/subscriber-workspace/management/history?include_skipped=true&operation=STATUS&page_size=1'
        for status, receipt in zip(('ELIGIBLE','CONFLICT'),source,strict=True):
            data = self.client.get(path+'&undo_status='+status).json()
            self.assertEqual(data['total'],1)
            self.assertEqual(data['items'][0]['request_id'],receipt['request_id'])
            self.assertEqual(data['items'][0]['undo_status'],status)
            self.assertEqual(self.client.get(path+'&undo_status='+status+'&page=2').json()['items'],[])

    def test_concurrent_group_undo_replay_and_competing_request(self):
        accounts = [self.create()[1] for _ in range(2)]
        source = self.post('/subscriber-workspace/management/execute',
                           {'entries':[self.operation(row,'STATUS','PAUSED') for row in accounts]}).json()['results']
        entries = [self.undo_command(response) for response in source]
        payload = UndoOperations.model_validate({'confirmed':True,'entries':entries})
        competing = UndoOperations.model_validate({'confirmed':True,'entries':[{**e,'request_id':str(uuid4())} for e in entries]})
        baseline = self.counts()
        with ThreadPoolExecutor(max_workers=3) as pool:
            first,replay,other = list(pool.map(lambda command:self.ops.execute_undo(command.entries,self.user),
                                               (payload,payload,competing)))
        self.assertEqual(first, replay)
        self.assertEqual({tuple(r['success'] for r in result) for result in (first,other)}, {(True,True),(False,False)})
        self.assertEqual(self.counts(),(baseline[0],baseline[1]+4))
        for account in accounts:
            current = self.client.get('/api/v1/subscriber-center/'+account['id']).json()['item']
            self.assertEqual((current['status'],current['revision']),('ACTIVE',3))

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
