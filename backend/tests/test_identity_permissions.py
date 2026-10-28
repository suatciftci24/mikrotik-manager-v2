from copy import deepcopy
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch,MagicMock
from uuid import uuid4
import asyncio,json
from fastapi import HTTPException
from pydantic import ValidationError
from app.services import identity
from app.services.demo_subscriptions import DemoChangeError
from app.core import security,authorization as az
from app.services.demo_data import ROUTERS,SUBSCRIBERS
from app.api.v1 import routers,subscribers,dashboard,reports,mikajani,alarms
from app.main import invalid_request

def user(ids=None,role='ADMIN',**flags):
    value=identity.bootstrap();value['id']='demo-test-user';value['role']=role
    value['permissions']={r['id']:{name:flags.get(name,True if role=='ADMIN' else name not in az.WRITE_FLAGS) for name in az.PERMISSIONS} for r in ROUTERS if ids is None or r['id'] in ids}
    return identity.public_user(value)

class IdentityTests(TestCase):
    def test_password_hash_is_salted_and_public_projection_has_no_credentials(self):
        secret='synthetic-password-'+str(uuid4());first=identity.hash_password(secret);second=identity.hash_password(secret)
        self.assertNotEqual(first,second);self.assertTrue(identity.verify_password(secret,first));self.assertFalse(identity.verify_password('wrong',first))
        self.assertNotIn(secret,first)
        account=identity.bootstrap();account['password_hash']=first
        public=identity.public_user(account)
        self.assertNotIn('password_hash',public);self.assertNotIn(secret,json.dumps(public))

    def test_same_session_rereads_permissions_and_role_without_caching(self):
        account=identity.bootstrap();account['password_hash']=identity.hash_password('test-pass-12')
        with patch.object(security,'find_user',side_effect=lambda *args,**kwargs:deepcopy(account)):
            token=security.login_demo('demo','test-pass-12')
            self.addCleanup(security.logout_demo,token)
            self.assertEqual(len(az.allowed(security.current_demo_user(token))),len(ROUTERS))
            account['permissions']={};account['role']='VIEWER'
            changed=security.current_demo_user(token)
            self.assertEqual(changed['role_code'],'VIEWER');self.assertEqual(az.allowed(changed),set())
            account['active']=False
            with self.assertRaises(HTTPException) as denied:security.current_demo_user(token)
            self.assertEqual(denied.exception.status_code,401)

    def test_last_active_admin_self_demotion_and_stale_revision_are_blocked(self):
        old=identity.bootstrap()
        def payload(**extra):return identity.UserChange(request_id=str(uuid4()),name=old['name'],email=old['email'],role=extra.get('role','VIEWER'),active=extra.get('active',True),permissions={},expected_revision=extra.get('revision',0),confirmed=True)
        for actor,count,command in [('other',1,payload()),('demo-user',2,payload()),('other',2,payload(revision=1)),('demo-user',2,payload(role='ADMIN',active=False)),('demo-user',2,payload(role='ADMIN'))]:
            with self.assertRaises(DemoChangeError):identity.transition(old,command,actor,count)
        result=identity.transition(old,payload(), 'other',2)
        self.assertEqual(result['role'],'VIEWER');self.assertEqual(result['revision'],1);self.assertEqual(old['role'],'ADMIN')

    def test_viewer_cannot_be_assigned_write_flags_and_unknown_routers_fail(self):
        base=dict(request_id=str(uuid4()),name='Synthetic',email='test@local.test',role='VIEWER',active=True,expected_revision=0,confirmed=True)
        for grants in [{ROUTERS[0]['id']:{'can_view':True,'can_manage_pppoe':True}},{'foreign':{'can_view':True}}]:
            with self.assertRaises(ValidationError):identity.UserChange(**base,permissions=grants)
        with self.assertRaises(ValidationError):identity.UserCreate(**base,permissions={},username='synthetic',password='short')

    def test_validation_response_does_not_echo_password_or_model_input(self):
        secret='never-echo-this-password'
        error=SimpleNamespace(errors=lambda:[dict(loc=('body','password'),msg='Field invalid',type='value_error',input=secret,ctx={'input':secret})])
        response=asyncio.run(invalid_request(None,error))
        self.assertNotIn(secret,response.body.decode());self.assertEqual(response.status_code,422)

    def test_missing_initialized_identity_table_never_restores_legacy_admin(self):
        adapter=MagicMock();connection=adapter.engine.connect.return_value.__enter__.return_value
        connection.execute.return_value.scalar_one.side_effect=[None,'true']
        with patch.object(identity,'adapter',return_value=adapter):
            from app.services.demo_subscriptions import DemoStorageUnavailable
            with self.assertRaises(DemoStorageUnavailable):identity.find_user('demo-user')

    def test_backend_session_lifetime_is_enforced_independently_of_cookie(self):
        account=identity.bootstrap()
        with patch.object(security,'find_user',return_value=account),patch.object(security.time,'monotonic',return_value=0):
            token=security.login_demo('demo','demo-only')
        self.addCleanup(security.logout_demo,token)
        with patch.object(security.time,'monotonic',return_value=8*60*60+1),patch.object(security,'find_user') as lookup:
            with self.assertRaises(HTTPException):security.current_demo_user(token)
            lookup.assert_not_called()

class ScopeTests(TestCase):
    def setUp(self):
        self.rid=ROUTERS[0]['id'];self.other=ROUTERS[1]['id'];self.user=user([self.rid]);self.items=deepcopy(SUBSCRIBERS)
        self.own=next(row for row in self.items if az.router_id(row)==self.rid)
        self.foreign=next(row for row in self.items if az.router_id(row)==self.other)
        self.store=Mock();self.store.list_items.return_value=self.items
        self.store.detail.side_effect=lambda id:next((dict(item=row,history=[{'id':'audit-secret'}],is_demo=True,persistence='local-postgresql-demo') for row in self.items if row['id']==id),None)
        self.patch=patch('app.services.demo_subscriptions.store',self.store);self.patch.start();self.addCleanup(self.patch.stop)

    def test_router_subscriber_and_dashboard_totals_are_scoped(self):
        listed=routers.list_routers(self.user);self.assertEqual([r['id'] for r in listed['items']],[self.rid]);self.assertEqual(listed['total'],1)
        rows=subscribers.list_subscribers(self.user)
        self.assertTrue(all(az.router_id(row)==self.rid for row in rows['items']))
        summary=dashboard.dashboard_summary(self.user)['summary']
        self.assertEqual(summary['router_count'],1);self.assertEqual(summary['subscribers_total'],rows['total'])
        for id in (self.other,'nonexistent'):
            with self.assertRaises(HTTPException) as error:routers.get_router(id,self.user)
            self.assertEqual(error.exception.status_code,404)

    def test_hidden_subscriber_and_write_targets_are_not_leaked(self):
        for id in (self.foreign['id'],'nonexistent'):
            with self.assertRaises(HTTPException) as error:subscribers.get_subscriber(id,self.user)
            self.assertEqual(error.exception.status_code,404)
        visible=user([self.rid],can_manage_pppoe=False)
        with self.assertRaises(HTTPException) as error:az.subscriber_for(visible,self.own['id'],'can_manage_pppoe')
        self.assertEqual(error.exception.status_code,403)

    def test_batch_spoofed_router_is_rejected_before_any_partial_write(self):
        entry=lambda id:SimpleNamespace(item_id=id,change=SimpleNamespace(action='EXTEND',router_id=self.rid,request_id=str(uuid4())))
        batch=SimpleNamespace(entries=[entry(self.own['id']),entry(self.foreign['id'])])
        with self.assertRaises(HTTPException):subscribers.quick_batch(batch,self.user)
        self.store.change_expiry.assert_not_called()

    def test_no_report_permission_strips_history_and_saved_metadata(self):
        viewer=user([self.rid],role='VIEWER',can_view_reports=False)
        data=subscribers.get_subscriber(self.own['id'],viewer)
        self.assertEqual(data['history'],[]);self.assertFalse(data['history_available']);self.assertIsNone(data['item']['demo_report'])
        self.assertFalse(data['item']['can_manage_pppoe'])
        with self.assertRaises(HTTPException):reports.report_inventory(viewer)

    def test_mika_uses_only_permitted_source_and_scenarios_are_closed(self):
        from app.services.mikajani import analyze
        with patch.object(mikajani,'project_saved',return_value=[]) as project:
            result=mikajani.analysis(None,self.user)
            self.assertEqual([r.router_id for r in result.health],[self.rid])
            self.assertTrue(all(az.router_id(row)==self.rid for row in project.call_args.args[1]))
        viewer=user([self.rid],role='VIEWER')
        with self.assertRaises(HTTPException):mikajani.analysis('central',viewer)
        with self.assertRaises(HTTPException):mikajani.analysis(None,user([self.rid],can_use_mikajani=False))

    def test_report_sql_scope_is_bound_before_counts_and_pagination(self):
        self.store.report_records.return_value=(self.items,[],0,[])
        with patch.object(reports,'project_report',return_value={}) as project:
            reports.operations('2026-10-01','2026-10-28',page=2,page_size=25,user=self.user)
        self.assertEqual([r['id'] for r in self.store.report_records.call_args.args[-1]],[self.rid])
        self.assertEqual(self.store.report_records.call_args.args[-2],25)
        self.assertTrue(all(az.router_id(row)==self.rid for row in project.call_args.args[0]))
        self.assertEqual([r['id'] for r in project.call_args.args[1]],[self.rid])
        with self.assertRaises(HTTPException) as error:reports.operations('2026-10-01','2026-10-28',router_id=self.other,page=1,page_size=25,user=self.user)
        self.assertEqual(error.exception.status_code,404)

    def test_archived_alarm_snapshots_cannot_leak_cross_router_mika_evidence(self):
        snapshot=dict(router_id=self.rid,mika=dict(affected_router_ids=[self.rid,self.other],evidence='foreign router evidence'))
        self.store.alarm_snapshot.return_value=(self.items,[dict(alarm_id='secret',source_snapshot=snapshot)],True)
        with patch.object(alarms,'project_alarms',return_value=([],{})) as project:
            alarms.source(self.user)
        self.assertEqual(project.call_args.args[2],[])
        self.assertEqual([r['id'] for r in project.call_args.args[1]],[self.rid])
        self.assertTrue(all(az.router_id(row)==self.rid for row in project.call_args.args[0]))

    def test_deny_by_default_and_explicit_router_id_never_uses_name_fallback(self):
        self.assertEqual(az.allowed({'is_demo':True}),set())
        hidden={**self.own,'router_id':'foreign','router_name':ROUTERS[0]['name']}
        self.assertEqual(az.items_for([hidden],self.user),[])
        self.assertEqual(az.allowed(user([self.rid],role='VIEWER',can_manage_pppoe=True),'can_manage_pppoe'),set())

    def test_scoped_admin_cannot_enumerate_global_user_or_router_permission_metadata(self):
        with self.assertRaises(HTTPException) as error:security.current_admin(self.user)
        self.assertEqual(error.exception.status_code,403)
        full=user();self.assertEqual(security.current_admin(full),full)
        with self.assertRaises(HTTPException):security.current_user_mutator(full,None)
        self.assertEqual(security.current_user_mutator(full,'user-management'),full)

    def test_native_audit_query_binds_scope_in_count_and_page_queries(self):
        from sqlalchemy.engine import make_url
        from app.adapters.demo_subscriptions import PostgresDemoStore
        engine=MagicMock();engine.url=make_url('postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2')
        store=PostgresDemoStore(engine);connection=engine.connect.return_value.execution_options.return_value.__enter__.return_value
        connection.execute.return_value.scalars.return_value=[];connection.execute.return_value.mappings.return_value=[];connection.execute.return_value.scalar_one.return_value=0
        with patch.object(store,'_verify'):
            store.report_records(datetime.now(timezone.utc),datetime.now(timezone.utc),datetime.now(timezone.utc),'','','','',25,25,[ROUTERS[0]])
        queries=connection.execute.call_args_list
        self.assertTrue(all('scope_ids' in str(call.args[0]) for call in queries if 'JOIN v2_demo.subscribers' in str(call.args[0])))
        self.assertEqual(queries[-1].args[1]['scope_ids'],[self.rid]);self.assertEqual(queries[-1].args[1]['offset'],25)
