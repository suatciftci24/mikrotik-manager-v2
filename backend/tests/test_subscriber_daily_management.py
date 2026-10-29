"""Daily operations on isolated synthetic transactions. No device/radius IO."""
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
from fastapi import HTTPException
import test_subscriber_center as cases
from app.models.router_workspace import RouterWorkspaceRecord as Router
from app.services.subscriber_operations import SubscriberOperationsService
from app.schemas.subscriber_management_center import SubscriberOperation,SubscriberOperations,OperationResults
from app.api.v1 import subscriber_center as routes

class DailyManagement(cases.SubscriberTransactions):
    def setUp(self):
        super().setUp();self.ops=SubscriberOperationsService(self.sessions,lambda s:None)
    def operation(self,item,operation,value=None,days=None,**changes):
        values=dict(request_id=uuid4(),item_id=item.id,expected_revision=item.revision,expected_router_id=item.router_id,expected_source=item.source,expected_expires_on=item.expires_on.isoformat() if item.expires_on else None,operation=operation,value=value,days=days,confirmed=True);values.update(changes);return SubscriberOperation(**values)
    def other_router(self):
        id='demo-managed-router-'+str(uuid4())
        with self.sessions.begin() as s:s.add(Router(id=id,kind='DEMO_ROUTER',revision=1,fields={'name':'Second router','model':'Test','site':'Other'}))
        return id
    def test_pppoe_hotspot_edit_plan_status_expire_and_30_60_90_extensions(self):
        for access in ('PPPOE','HOTSPOT'):
            item=self.workspace.save(self.command(access,username=access.lower()+'.test',status='ACTIVE'),'actor')
            for operation,value in [('EDIT','Updated Name'),('PLAN','Demo 900'),('STATUS','PAUSED'),('STATUS','ACTIVE'),('EXPIRE','2027-04-01')]:
                result=self.ops.execute(self.operation(item,operation,value),'actor');self.assertTrue(result['success'],result)
                item=self.workspace.detail(item.id).item
            first=None
            for days in (30,60,90):
                expected=(max(item.expires_on,datetime.now(ZoneInfo('Europe/Istanbul')).date())+timedelta(days=days)).isoformat()
                command=self.operation(item,'EXTEND',expected,days);result=self.ops.execute(command,'actor');self.assertTrue(result['success']);self.assertEqual(result['values']['expires_on'],expected)
                self.assertEqual(self.ops.execute(command,'actor'),result)
                if first is None:first=(command,result)
                item=self.workspace.detail(item.id).item;self.assertEqual(item.status,'ACTIVE')
            self.assertEqual(self.ops.execute(first[0],'actor'),first[1])  # Durable historical receipt even after later edits.
            reopened=type(self.workspace)(self.sessions,lambda s:None);self.assertEqual(reopened.detail(item.id).item,item)
    def test_expired_active_account_uses_turkey_today_and_unknown_is_not_guessed(self):
        today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
        item=self.workspace.save(self.command(status='ACTIVE',expires_on=(today-timedelta(days=2)).isoformat()),'actor')
        result=self.ops.execute(self.operation(item,'EXTEND',(today+timedelta(days=90)).isoformat(),90),'actor')
        self.assertTrue(result['success']);current=self.workspace.detail(item.id).item;self.assertEqual(current.status,'ACTIVE')
        self.assertTrue(self.ops.execute(self.operation(current,'EXPIRE',None),'actor')['success'])
        current=self.workspace.detail(item.id).item
        failed=self.ops.execute(self.operation(current,'EXTEND',(today+timedelta(days=30)).isoformat(),30),'actor')
        self.assertFalse(failed['success']);self.assertIsNone(self.workspace.detail(item.id).item.expires_on)
    def test_router_move_preserves_source_kind_and_updates_both_relations(self):
        item=self.workspace.save(self.command('HOTSPOT',source='RADIUS'),'actor');target=self.other_router()
        result=self.ops.execute(self.operation(item,'ROUTER',target),'actor');self.assertTrue(result['success']);self.assertEqual(result['previous_router_id'],self.router_id)
        saved=self.workspace.detail(item.id).item;self.assertEqual(saved.router_id,target);self.assertEqual(saved.source,'RADIUS');self.assertEqual(saved.access_type,'HOTSPOT')
        self.assertEqual(self.workspace.list(router_id=self.router_id)['total'],0);self.assertEqual(self.workspace.list(router_id=target)['total'],1)
        event=self.workspace.detail(item.id).history[0];self.assertEqual(event.previous_values['router_id'],self.router_id);self.assertEqual(event.new_values['router_id'],target)
    def test_bulk_cross_router_partial_failure_receipts_and_retry(self):
        first=self.workspace.save(self.command(username='one.test'),'actor');target=self.other_router();second=self.workspace.save(self.command('HOTSPOT',username='two.test',router_id=target),'actor')
        payload=SubscriberOperations(entries=[self.operation(first,'STATUS','ACTIVE'),self.operation(second,'STATUS','ACTIVE',expected_revision=999)])
        with patch.object(routes,'operations',self.ops):
            result=routes.manage(payload,{'id':'actor'});OperationResults.model_validate(result)
            self.assertEqual([r['success'] for r in result['results']],[True,False]);self.assertEqual(routes.manage(payload,{'id':'actor'}),result)
        self.assertEqual(self.workspace.detail(second.id).item.status,'PAUSED');self.assertEqual(self.workspace.detail(second.id).history[0].result,'FAILED')
        self.assertEqual(self.ops.history(result='FAILED')['total'],1)
        self.assertEqual(self.ops.history(result='SUCCESS')['total'],3)  # Two creates + one status change.
        self.assertEqual(self.ops.history(page=2,page_size=100)['items'],[])
    def test_audit_failure_and_conflicting_request_do_not_mutate(self):
        item=self.workspace.save(self.command(),'actor');baseline=self.workspace.detail(item.id)
        command=self.operation(item,'PLAN','Demo 800')
        with patch.object(self.ops,'audit',side_effect=SQLAlchemyError('CANARY')):
            result=self.ops.execute(command,'actor');self.assertFalse(result['success']);self.assertFalse(result['recorded'])
        self.assertEqual(self.workspace.detail(item.id),baseline)
        applied=self.ops.execute(command,'actor');self.assertTrue(applied['success'])
        conflict=self.operation(item,'PLAN','Different',request_id=command.request_id)
        failed=self.ops.execute(conflict,'actor');self.assertFalse(failed['success']);self.assertFalse(failed['recorded']);self.assertEqual(self.workspace.detail(item.id).item.plan,'Demo 800')
    def test_real_target_rejected_and_no_effect_on_source_or_original_router(self):
        item=self.workspace.save(self.command(),'actor')
        result=self.ops.execute(self.operation(item,'ROUTER','registered-'+str(uuid4())),'actor');self.assertFalse(result['success']);self.assertTrue(result['recorded'])
        self.assertEqual(self.workspace.detail(item.id).item.router_id,self.router_id)
        values=self.operation(item,'STATUS','ACTIVE').model_dump(mode='json');values['item_id']='registered-'+str(uuid4())
        with self.assertRaises(ValidationError):SubscriberOperation(**values)

class DailyContracts(TestCase):
    def test_unauthorized_or_unconfirmed_or_oversized_batches_rejected(self):
        admin={'id':'demo-user','is_demo':True,'role_code':'ADMIN','can_manage_users':True}
        with self.assertRaises(HTTPException):routes.mutator({**admin,'role_code':'VIEWER'},'subscriber-workspace')
        with self.assertRaises(HTTPException):routes.mutator(admin,'wrong')
        with self.assertRaises(ValidationError):SubscriberOperations(entries=[])
        value=dict(request_id=uuid4(),item_id='demo-managed-sub-'+str(uuid4()),expected_router_id='demo-managed-router-'+str(uuid4()),expected_revision=1,expected_source='LOCAL',operation='STATUS',value='ACTIVE',confirmed=1)
        with self.assertRaises(ValidationError):SubscriberOperation(**value)
    def test_static_action_routes_not_shadowed_by_record_ids(self):
        from app.main import app
        from starlette.routing import Match
        for method,path,name in [('POST','/api/v1/subscriber-workspace/management/execute','manage'),('GET','/api/v1/subscriber-workspace/management/history','history')]:
            self.assertIn(method.lower(),app.openapi()['paths'][path])
            matched=[r for r in routes.router.routes if r.matches({'type':'http','method':method,'path':path.removeprefix('/api/v1'),'root_path':''})[0]==Match.FULL]
            self.assertEqual(matched[0].name,name)

def load_tests(loader,tests,pattern):
    import unittest
    suite=unittest.TestSuite(DailyManagement(name) for name in DailyManagement.__dict__ if name.startswith('test_'));suite.addTests(loader.loadTestsFromTestCase(DailyContracts));return suite
