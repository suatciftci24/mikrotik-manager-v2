"""Disposable PG16, Unix socket only, peer auth; no V2/V1/live DB or device IO."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import getpass
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'backend'))
from sqlalchemy import create_engine,text
from sqlalchemy.engine import URL
from fastapi.testclient import TestClient
from app.main import app
from app.services import identity,system_settings as settings,preferences_repair as maintenance
from app.core import security
from app.services.first_admin import FirstAdminInput,create_local_admin

spec=importlib.util.spec_from_file_location('repair_install',ROOT/'deploy/fresh-v2-pilot/manage.py')
install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)
BACKUP='a'*64


class PreferencesRepairPostgres(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bin=Path('/usr/lib/postgresql/16/bin')
        cls.temp=tempfile.TemporaryDirectory(prefix='v2-preferences-synthetic-')
        cls.directory=Path(cls.temp.name);cls.pg=cls.directory/'pg';cls.sock=cls.directory/'socket';cls.sock.mkdir(mode=0o700)
        cls.user=getpass.getuser()
        cls.started=False
        try:
            subprocess.run([str(cls.bin/'initdb'),'-D',str(cls.pg),'-U',cls.user,'--auth-local=peer','--auth-host=reject','--no-instructions','--locale=C.UTF-8'],check=True,capture_output=True)
            subprocess.run([str(cls.bin/'pg_ctl'),'-D',str(cls.pg),'-l',str(cls.directory/'postgres.log'),'-o',f"-h '' -k {cls.sock} -p 55489 -F",'-w','start'],check=True,capture_output=True,timeout=20)
            cls.started=True
            cls.base=create_engine(URL.create('postgresql+psycopg',username=cls.user,database='postgres',query={'host':str(cls.sock),'port':'55489'}),hide_parameters=True)
        except Exception:
            cls.tearDownClass();raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'base'):cls.base.dispose()
        if cls.started:
            subprocess.run([str(cls.bin/'pg_ctl'),'-D',str(cls.pg),'-m','fast','-w','stop'],check=True,capture_output=True,timeout=20)
        cls.temp.cleanup()

    def setUp(self):
        self.db='synthetic_'+uuid4().hex
        with self.base.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+self.db))
        self.engine=create_engine(URL.create('postgresql+psycopg',username=self.user,database=self.db,query={'host':str(self.sock),'port':'55489'}),hide_parameters=True,connect_args={'options':'-c lock_timeout=5000 -c statement_timeout=10000'})
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as c:
            for file in ['002_demo_storage.sql','004_demo_identity.sql','005_demo_settings.sql','009_first_local_admin.sql']:
                install.execute_script(c,(ROOT/'migrations/versions'/file).read_text())
            self.secret='synthetic-password-only-2026'
            payload=FirstAdminInput(username='synthetic-admin',name='Synthetic Admin',email='synthetic@example.invalid',password=self.secret)
            self.actor=create_local_admin(c,payload,os.getuid())['id']
            c.execute(text("INSERT INTO v2_demo.subscribers(id,payload) VALUES ('demo-sub-synthetic',CAST(:p AS jsonb))"),{'p':json.dumps({'id':'demo-sub-synthetic','is_demo':True,'source':'LOCAL','name':'Synthetic subscriber'})})
        def verify(c):
            self.assertEqual(c.execute(text('SELECT marker FROM v2_demo.schema_state WHERE version=1')).scalar_one(),'mikrotik-manager-v2-synthetic-only')
        self.store=SimpleNamespace(engine=self.engine,_verify=verify)
        self.patcher=patch.object(identity,'adapter',return_value=self.store);self.patcher.start();self.addCleanup(self.patcher.stop)
        self.client=TestClient(app);self.addCleanup(self.client.close)
        response=self.client.post('/api/v1/auth/login',json={'username':'synthetic-admin','password':self.secret})
        self.assertEqual(response.status_code,200)
        self.addCleanup(lambda:self.client.post('/api/v1/auth/logout'))

    def run_repair(self,request_id=None):
        with self.engine.begin() as c:return maintenance.repair(c,self.actor,request_id or uuid4(),BACKUP)

    def rows(self):
        with self.engine.connect() as c:
            return list(c.execute(text('SELECT payload,revision,updated_at FROM v2_demo.settings_records ORDER BY id')))

    def protected(self):
        with self.engine.connect() as c:
            return {table:list(c.execute(text('SELECT to_jsonb(t) FROM v2_demo.'+table+' t ORDER BY to_jsonb(t)::text'))) for table in ['users','user_audit','first_admin_setup','subscribers','events','requests','schema_state']}

    def test_new_empty_install_creates_default_and_verified_read(self):
        with self.engine.begin() as c:
            install.initialize_preferences(c);install.verify_preferences(c)
        r=self.client.get('/api/v1/preferences')
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['values'],settings.Values().model_dump())

    def test_missing_repair_closes_503_and_preserves_admin_demo_and_audits(self):
        before=self.protected();r=self.client.get('/api/v1/preferences')
        self.assertEqual(r.status_code,503);self.assertEqual(r.json()['code'],'DEFAULT_SETTINGS_MISSING')
        self.assertEqual(self.rows(),[])  # A GET did not create anything.
        created=self.run_repair()
        self.assertTrue(created['changed']);self.assertEqual(self.client.get('/api/v1/preferences').status_code,200)
        self.assertEqual(self.protected(),before)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT count(*) FROM v2_demo.settings_audit')).scalar_one(),1)
            event=c.execute(text('SELECT response FROM v2_demo.settings_audit')).scalar_one()
            self.assertEqual(event['operation'],'DEFAULT_SETTINGS_REPAIR')
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code,200)

    def test_second_run_preserves_customized_settings_revision_and_timestamp(self):
        self.run_repair()
        with self.engine.begin() as c:c.execute(text("UPDATE v2_demo.settings_records SET payload=payload || '{\"theme\":\"dark\"}'::jsonb,revision=7 WHERE id='default'"))
        before=self.rows();result=self.run_repair()
        self.assertFalse(result['changed']);self.assertEqual(self.rows(),before)
        with self.engine.connect() as c:self.assertEqual(c.execute(text('SELECT count(*) FROM v2_demo.settings_audit')).scalar_one(),1)

    def test_eight_concurrent_repairs_create_one_row_and_one_audit(self):
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:self.run_repair(),range(8)))
        self.assertEqual(sum(r['changed'] for r in results),1)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT count(*) FROM v2_demo.settings_records WHERE id='default'")).scalar_one(),1)
            self.assertEqual(c.execute(text('SELECT count(*) FROM v2_demo.settings_audit')).scalar_one(),1)

    def test_invalid_existing_record_is_not_overwritten_and_schema_missing_distinct(self):
        with self.engine.begin() as c:c.execute(text("INSERT INTO v2_demo.settings_records(id,payload) VALUES ('default','{\"theme\":\"invalid\"}')"))
        before=self.rows()
        with self.assertRaisesRegex(maintenance.RepairBlocked,'DEFAULT_SETTINGS_INVALID'):self.run_repair()
        self.assertEqual(self.rows(),before)
        r=self.client.get('/api/v1/preferences');self.assertEqual(r.status_code,503);self.assertEqual(r.json()['code'],'SETTINGS_RECORD_INVALID')
        # Explicitly fake only catalog availability; no destructive schema changes.
        with patch.object(settings,'ready',return_value=False):
            r=self.client.get('/api/v1/preferences');self.assertEqual(r.status_code,503);self.assertEqual(r.json()['code'],'SETTINGS_SCHEMA_MISSING')

    def test_real_authorization_read_write_and_transactional_audit(self):
        self.run_repair()
        with TestClient(app) as anon:self.assertEqual(anon.get('/api/v1/preferences').status_code,401)
        command={'request_id':str(uuid4()),'expected_revision':0,'confirmed':True,'values':settings.Values(app_name='Synthetic customized',theme='dark').model_dump()}
        self.assertEqual(self.client.post('/api/v1/system/settings',json=command).status_code,403)
        r=self.client.post('/api/v1/system/settings',headers={'X-V2-Demo-Action':'system-settings'},json=command)
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/api/v1/preferences').json()['values']['app_name'],'Synthetic customized')
        personal={'request_id':str(uuid4()),'expected_revision':0,'confirmed':True,'values':{'page_size':10}}
        self.assertEqual(self.client.post('/api/v1/preferences',headers={'X-V2-Demo-Action':'ui-preferences'},json=personal).status_code,200)
        self.assertEqual(self.client.get('/api/v1/preferences').json()['values']['page_size'],10)
        with self.engine.begin() as c:c.execute(text("UPDATE v2_demo.users SET role='VIEWER' WHERE id=:id"),{'id':self.actor})
        command['request_id']=str(uuid4());command['expected_revision']=1
        self.assertEqual(self.client.post('/api/v1/system/settings',headers={'X-V2-Demo-Action':'system-settings'},json=command).status_code,403)
        with self.assertRaisesRegex(maintenance.RepairBlocked,'LOCAL_ADMIN_REQUIRED'):self.run_repair()

    def test_actual_failed_db_connection_returns_database_503_without_fake_success(self):
        self.run_repair()
        missing=self.directory/('nonexistent-'+uuid4().hex)
        broken=create_engine(URL.create('postgresql+psycopg',username=self.user,database=self.db,query={'host':str(missing),'port':'55489'}),hide_parameters=True,connect_args={'connect_timeout':1})
        try:
            with patch.object(identity,'adapter',return_value=SimpleNamespace(engine=broken,_verify=lambda c:None)):
                r=self.client.get('/api/v1/preferences')
            self.assertEqual(r.status_code,503);self.assertEqual(r.json()['code'],'DATABASE_UNAVAILABLE')
            self.assertNotIn(str(missing),r.text);self.assertNotIn(self.secret,r.text)
        finally:broken.dispose()

    def test_audit_failure_rolls_back_default_insert(self):
        with self.engine.begin() as c:
            c.execute(text("CREATE FUNCTION v2_demo.synthetic_audit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic'; END $$"))
            c.execute(text('CREATE TRIGGER synthetic_audit_fail BEFORE INSERT ON v2_demo.settings_audit FOR EACH ROW EXECUTE FUNCTION v2_demo.synthetic_audit_fail()'))
        from sqlalchemy.exc import SQLAlchemyError
        with self.assertRaises(SQLAlchemyError):self.run_repair()
        self.assertEqual(self.rows(),[])
        self.assertEqual(self.client.get('/api/v1/preferences').json()['code'],'DEFAULT_SETTINGS_MISSING')

    def test_conditional_rollback_restores_only_absent_row_and_refuses_later_edit(self):
        before=self.protected();repair_id=uuid4();self.run_repair(repair_id);rollback_id=uuid4()
        with self.engine.begin() as c:result=maintenance.rollback(c,self.actor,repair_id,rollback_id)
        self.assertEqual(result['status'],'ROLLED_BACK');self.assertEqual(self.rows(),[]);self.assertEqual(before,self.protected())
        with self.engine.begin() as c:self.assertFalse(maintenance.rollback(c,self.actor,repair_id,rollback_id)['changed'])
        second=uuid4();self.run_repair(second)
        with self.engine.begin() as c:c.execute(text("UPDATE v2_demo.settings_records SET revision=revision+1 WHERE id='default'"))
        with self.assertRaisesRegex(maintenance.RepairBlocked,'DEFAULT_CHANGED_ROLLBACK_REFUSED'):
            with self.engine.begin() as c:maintenance.rollback(c,self.actor,second,uuid4())
        self.assertEqual(self.client.get('/api/v1/preferences').status_code,200)

    def test_custom_backup_restores_into_disposable_database(self):
        before=self.protected();dump=self.directory/(self.db+'.dump')
        subprocess.run([str(self.bin/'pg_dump'),'-h',str(self.sock),'-p','55489','-U',self.user,'-d',self.db,'-Fc','-f',str(dump)],check=True,capture_output=True)
        restored='restore_'+uuid4().hex
        with self.base.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+restored))
        subprocess.run([str(self.bin/'pg_restore'),'-h',str(self.sock),'-p','55489','-U',self.user,'-d',restored,'--exit-on-error',str(dump)],check=True,capture_output=True)
        restored_engine=create_engine(URL.create('postgresql+psycopg',username=self.user,database=restored,query={'host':str(self.sock),'port':'55489'}),hide_parameters=True)
        try:
            old=self.engine;self.engine=restored_engine
            try:self.assertEqual(self.protected(),before);self.assertEqual(self.rows(),[])
            finally:self.engine=old
        finally:restored_engine.dispose()


class MaintenanceGates(TestCase):
    def test_prepared_stream_needs_explicit_approval_before_any_connection(self):
        import ast
        import io
        spec=importlib.util.spec_from_file_location('prepare_repair',ROOT/'deploy/fresh-v2-pilot/prepare-preferences-repair.py')
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        code=prepare.bundle();ast.parse(code)
        with patch.object(sys,'argv',['-','apply','--request-id',str(uuid4())]),patch('sqlalchemy.create_engine') as connect,patch('sys.stdout',new_callable=io.StringIO) as output:
            with self.assertRaises(SystemExit) as stopped:exec(compile(code,'<synthetic-reviewed-bundle>','exec'),{'__name__':'__main__'})
        self.assertEqual(stopped.exception.code,2);connect.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['status'],'BLOCKED')
