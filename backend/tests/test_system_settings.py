"""Socket-free transaction/authorization checks; not real PostgreSQL acceptance."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timezone
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from uuid import uuid4
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from fastapi import HTTPException
from app.services import system_settings as service,identity,system_health
from app.services.demo_subscriptions import DemoChangeError,DemoStorageUnavailable
from app.core.security import current_admin

class SQL:
    def __init__(self):
        self.rows={'default':dict(payload=service.Values().model_dump(),revision=0,updated_at=datetime.now(timezone.utc))};self.users={'demo-user':identity.bootstrap()};self.audit={};self.fail=False;self.ready=True;self.calls=[]
    @contextmanager
    def begin(self):
        old=deepcopy((self.rows,self.audit))
        try:yield self
        except BaseException:self.rows,self.audit=old;raise
    def execute(self,statement,p=None):
        sql=str(statement);p=p or {};self.calls.append(sql);value=None
        if 'to_regclass' in sql:value=self.ready
        elif 'SELECT * FROM v2_demo.users' in sql:value=self.users.get(p['id'])
        elif 'SELECT * FROM v2_demo.settings_audit' in sql:value=self.audit.get(p['id'])
        elif 'SELECT * FROM v2_demo.settings_records' in sql:value=self.rows.get(p['id'])
        elif sql.startswith('INSERT INTO v2_demo.settings_records'):
            self.rows[p['id']]=dict(payload=json.loads(p['values']),revision=self.rows.get(p['id'],{}).get('revision',0)+1,updated_at=datetime.now(timezone.utc));value=self.rows[p['id']]
        elif sql.startswith('INSERT INTO v2_demo.settings_audit'):
            if self.fail:raise OperationalError('INSERT',{},Exception('synthetic fault'))
            if p['id'] not in self.audit:self.audit[p['id']]=dict(fingerprint=p['fingerprint'],response=json.loads(p['response']),result='REJECTED' if "'REJECTED'" in sql else 'SUCCESS',actor_id=p['actor'],previous_values=json.loads(p['previous']),new_values=json.loads(p['new']))
        return SimpleNamespace(scalar_one=lambda:value,mappings=lambda:SimpleNamespace(one_or_none=lambda:value,one=lambda:value))

class SettingsTransactions(TestCase):
    def setUp(self):
        self.db=SQL();self.patcher=patch.object(identity,'adapter',return_value=SimpleNamespace(engine=self.db,_verify=Mock()));self.patcher.start();self.addCleanup(self.patcher.stop)
    def command(self,**values):return service.Command(request_id=uuid4(),expected_revision=0,confirmed=True,values=service.Values(**values))
    def test_commit_audit_and_same_request_replay(self):
        command=self.command(app_name='Test V2');first=service.save('default',command,'demo-user');self.assertEqual(service.save('default',command,'demo-user'),first);self.assertEqual(first['revision'],1);self.assertEqual(len(self.db.audit),1);self.assertEqual(next(iter(self.db.audit.values()))['previous_values']['app_name'],'MikroTik Manager V2')
    def test_reused_uuid_with_changed_values_conflicts(self):
        command=self.command();service.save('default',command,'demo-user');changed=command.model_copy(update={'values':service.Values(app_name='Other')})
        with self.assertRaises(DemoChangeError) as error:service.save('default',changed,'demo-user')
        self.assertEqual(error.exception.status_code,409);self.assertEqual(len(self.db.audit),1)
    def test_revision_conflict_is_audited_without_overwriting(self):
        service.save('default',self.command(),'demo-user');command=self.command(app_name='Stale')
        with self.assertRaises(DemoChangeError) as error:service.save('default',command,'demo-user')
        service.rejected('default',command,'demo-user',error.exception);service.rejected('default',command,'demo-user',error.exception)
        self.assertEqual(len(self.db.audit),2);self.assertEqual(self.db.rows['default']['revision'],1);self.assertEqual(self.db.audit[str(command.request_id)]['result'],'REJECTED')
    def test_audit_failure_rolls_back_record(self):
        self.db.fail=True
        with self.assertRaises(DemoStorageUnavailable):service.save('default',self.command(app_name='Changed'),'demo-user')
        self.assertEqual(self.db.rows['default']['revision'],0);self.assertEqual(self.db.audit,{})
    def test_actor_scope_and_revocation_rechecked_even_on_replay(self):
        command=self.command();service.save('default',command,'demo-user')
        for patch_values in [dict(role='VIEWER'),dict(active=False),dict(permissions={})]:
            original=deepcopy(self.db.users['demo-user']);self.db.users['demo-user'].update(patch_values)
            with self.assertRaises(DemoChangeError) as error:service.save('default',command,'demo-user')
            self.assertEqual(error.exception.status_code,403);self.db.users['demo-user']=original
        self.assertTrue(any('FOR SHARE' in sql for sql in self.db.calls))
    def test_personal_settings_are_own_only_and_do_not_change_defaults(self):
        self.db.users['demo-user']['role']='VIEWER';command=service.PersonalCommand(request_id=uuid4(),expected_revision=0,confirmed=True,values=service.Personal(notifications_enabled=False,page_size=10))
        response=service.save('user:demo-user',command,'demo-user',personal=True);self.assertFalse(response['values']['notifications_enabled']);self.assertEqual(self.db.rows['default']['revision'],0)
        with self.assertRaises(DemoChangeError):service.save('user:someone-else',command,'demo-user',personal=True)
    def test_missing_store_does_not_write(self):
        self.db.ready=False
        with self.assertRaises(DemoChangeError) as error:service.save('default',self.command(),'demo-user')
        self.assertEqual(error.exception.status_code,503);self.assertEqual(self.db.audit,{})
    def test_test_profile_changes_never_touch_active_default(self):
        id='demo-settings-'+str(uuid4());self.db.rows[id]=deepcopy(self.db.rows['default']);service.save(id,self.command(app_name='Isolated'),'demo-user');self.assertEqual(self.db.rows['default']['revision'],0);self.assertEqual(self.db.rows[id]['revision'],1)

class SettingsContracts(TestCase):
    def test_whitelist_rejects_unsafe_security_adapter_and_invalid_values(self):
        for values in [dict(cookie_secure=False),dict(session_timeout_seconds=0),dict(database_url='secret'),dict(timezone='UTC'),dict(page_size=100000),dict(notification_levels=['P1','P1']),dict(app_name='   '),dict(app_name='x\ny')]:
            with self.assertRaises(ValidationError):service.Values(**values)
    def test_personal_cannot_target_users_or_change_global_name(self):
        for values in [dict(user_id='other'),dict(app_name='Override'),dict(timezone='UTC')]:
            with self.assertRaises(ValidationError):service.Personal(**values)
        self.assertEqual(service.Personal().model_dump()['theme'],None)
    def test_viewer_and_restricted_admin_denied_by_existing_backend_guard(self):
        for user in [dict(role_code='VIEWER',can_manage_users=False),dict(role_code='ADMIN',can_manage_users=False)]:
            with self.assertRaises(HTTPException) as error:current_admin(user)
            self.assertEqual(error.exception.status_code,403)
    def test_security_policy_is_readonly_and_sources_are_disconnected(self):
        policy=system_health.security_policy();self.assertTrue(policy['read_only']);self.assertEqual(policy['session_timeout_seconds'],28800);self.assertTrue(policy['cookie_http_only']);self.assertEqual(policy['cookie_same_site'],'strict');self.assertEqual(system_health.sources()['radius'],'DISCONNECTED')
    def test_health_retains_real_last_success_and_unmeasured_unknown(self):
        with patch.object(system_health.demo_subscriptions,'store',SimpleNamespace(ping=Mock(return_value=True))):good=system_health.health()
        with patch.object(system_health.demo_subscriptions,'store',SimpleNamespace(ping=Mock(side_effect=DemoStorageUnavailable()))):bad=system_health.health()
        self.assertEqual(bad['checks']['database']['status'],'ERROR');self.assertEqual(bad['checks']['database']['last_success'],good['checks']['database']['last_success'])
        for key in ['ui','proxy','postgres_process','vite_process']:self.assertEqual(good['checks'][key]['status'],'UNKNOWN')
        self.assertNotIn('postgresql://',json.dumps(bad))
    def test_profile_id_does_not_accept_arbitrary_record_or_user(self):
        for id in ['user:demo-user','demo-settings-bad','../default','']:
            with self.assertRaises(DemoChangeError):service.profile_id(id)
    def test_reinitialize_preserves_existing_values_and_missing_initialized_store_blocks(self):
        from unittest.mock import MagicMock
        from app.demo_repair import ROOT,RepairBlocked
        for ready in [True,False]:
            engine=MagicMock();connection=engine.begin.return_value.__enter__.return_value;calls=[]
            def execute(statement,params=None):
                sql=str(statement);calls.append(sql)
                value=str(ROOT/'.local/postgres-v2-demo') if 'SHOW data_directory' in sql else 'true'
                return SimpleNamespace(scalar_one=lambda:value)
            connection.execute.side_effect=execute
            with patch.object(identity,'adapter',return_value=SimpleNamespace(engine=engine,_verify=Mock())),patch('app.demo_repair.preflight'),patch.object(identity,'ready',return_value=True),patch.object(service,'ready',return_value=ready),patch.object(service,'record',return_value={'values':{'app_name':'Preserved'}}):
                if ready:service.initialize()
                else:
                    with self.assertRaises(RepairBlocked):service.initialize()
            self.assertFalse(any('INSERT INTO v2_demo.settings_records' in sql for sql in calls))
    def test_admin_routes_share_backend_guard_and_mutation_requires_action_header(self):
        from app.api.v1 import system
        from fastapi.routing import APIRoute
        for route in system.router.routes:
            if isinstance(route,APIRoute) and route.path.startswith('/system/'):
                dependencies=[item.call for item in route.dependant.dependencies]
                self.assertTrue(current_admin in dependencies or system.mutator in dependencies,route.path)
        with self.assertRaises(HTTPException) as error:system.mutator({'role_code':'ADMIN','can_manage_users':True},None)
        self.assertEqual(error.exception.status_code,403)
    def test_notification_levels_filter_before_pagination_without_changing_ack_summary(self):
        from app.api.v1 import alarms
        from app.services.identity import public_user,bootstrap
        rows=[{'router_id':'r1','last_seen':None,'id':'test-'+str(i),'severity':level,'state':'OPEN','source_available':True,'notification_read':False} for i,level in enumerate(['P4','P1','P4','P2'])]
        with patch.object(alarms,'source',return_value=(rows,{},True)),patch.object(alarms,'public_alarm',side_effect=lambda row:row):
            result=alarms.list_alarms(levels='P1,P2',page=1,page_size=1,user=public_user(bootstrap()))
            self.assertEqual(result['total'],2);self.assertEqual(result['items'][0]['severity'],'P1');self.assertEqual(result['summary']['active'],4)
            empty=alarms.list_alarms(levels='NONE',page=1,page_size=10,user=public_user(bootstrap()));self.assertEqual(empty['total'],0)
            with self.assertRaises(HTTPException):alarms.list_alarms(levels='P9',page=1,page_size=10,user=public_user(bootstrap()))
    def test_real_migration_comments_are_not_split_into_executable_statements(self):
        """Run the real migration through initialization, including its comment semicolon."""
        from unittest.mock import MagicMock
        from app.demo_repair import ROOT
        engine=MagicMock();connection=engine.begin.return_value.__enter__.return_value
        calls=[];initialized=False;default={'values':{'app_name':'Existing customized name'},'revision':7}
        def execute(statement,params=None):
            nonlocal initialized
            sql=str(statement).strip();calls.append(sql)
            if 'SHOW data_directory' in sql:value=str(ROOT/'.local/postgres-v2-demo')
            elif 'to_jsonb' in sql:value='true' if initialized else None
            elif sql.startswith('INSERT INTO v2_demo.settings_records'):
                # First setup uses ON CONFLICT DO NOTHING, never overwrites an existing record.
                self.assertIn('ON CONFLICT DO NOTHING',sql);value=None
            else:
                self.assertTrue(sql.startswith(('SELECT ','CREATE TABLE ','ALTER TABLE ','UPDATE v2_demo.schema_state ','CREATE INDEX ')),sql)
                self.assertNotIn('--',sql)
                if sql.startswith('UPDATE v2_demo.schema_state '):initialized=True
                value=None
            return SimpleNamespace(scalar_one=lambda:value)
        connection.execute.side_effect=execute
        with patch.object(identity,'adapter',return_value=SimpleNamespace(engine=engine,_verify=Mock())),patch('app.demo_repair.preflight'),patch.object(identity,'ready',return_value=True),patch.object(service,'ready',return_value=True),patch.object(service,'record',return_value=default):
            service.initialize();service.initialize()
        self.assertEqual(sum(sql.startswith('CREATE TABLE ') for sql in calls),4)
        self.assertEqual(sum(sql.startswith('INSERT INTO v2_demo.settings_records') for sql in calls),1)
        self.assertFalse(any(sql.startswith(('DELETE','TRUNCATE','DROP','UPDATE v2_demo.settings_records','INSERT INTO v2_demo.users','UPDATE v2_demo.users')) for sql in calls))
        self.assertEqual(default['values']['app_name'],'Existing customized name');self.assertEqual(default['revision'],7)

    def test_each_acceptance_run_clones_existing_defaults_into_new_profile_only(self):
        from unittest.mock import MagicMock
        engine=MagicMock();connection=engine.begin.return_value.__enter__.return_value
        values=service.Values(app_name='Preserved customized V2',theme='dark',page_size=10).model_dump()
        before=deepcopy(values)
        with patch.object(service,'initialize') as setup,patch.object(identity,'adapter',return_value=SimpleNamespace(engine=engine,_verify=Mock())),patch.object(service,'record',return_value={'values':values,'revision':9}):
            first=service.prepare_acceptance();second=service.prepare_acceptance()
        self.assertNotEqual(first,second);self.assertEqual(setup.call_count,2)
        for call in connection.execute.call_args_list:
            sql=str(call.args[0]);params=call.args[1]
            self.assertTrue(sql.startswith('INSERT INTO v2_demo.settings_records'))
            self.assertIn(params['id'],[first,second]);self.assertNotEqual(params['id'],'default')
            self.assertEqual(json.loads(params['values']),before)
        self.assertEqual(values,before)
