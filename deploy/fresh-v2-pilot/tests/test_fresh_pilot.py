"""Synthetic/local-only checks. PostgreSQL uses single-user mode, never sockets."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path[:0] = [str(HERE),str(REPO/'backend')]
import manage
from sqlalchemy import text
from app.services.first_admin import FirstAdminInput, create_local_admin
from app.core import fresh_pilot


class Gates(unittest.TestCase):
    def test_order_checksums_and_no_down(self):
        _, manifest, sql = manage.check_sources()
        self.assertEqual(len(sql),9)
        self.assertFalse(any('down' in x['revision'] for x in manifest['migrations']))
        real = manage.checked_file
        def altered(path):
            data = real(path)
            return data+b' ' if path.name == manage.FILES[0] else data
        with patch.object(manage,'checked_file',side_effect=altered):
            with self.assertRaisesRegex(manage.Blocked,'CHECKSUM'):
                manage.check_sources()

    def test_nonempty_or_previous_ledger_blocked_before_writes(self):
        class Result:
            def scalars(self):return iter(['public','v2_migrations'])
        class Connection:
            def execute(self, statement, params):
                self.query = str(statement)
                return Result()
        c=Connection()
        with self.assertRaisesRegex(manage.Blocked,'NONEMPTY_TARGET'):
            manage.require_empty(c)
        self.assertTrue(c.query.startswith('SELECT'))

    def test_populated_public_table_and_wrong_cluster_are_rejected(self):
        class Result:
            def __init__(self,value):self.value=value
            def scalars(self):return iter(self.value)
            def scalar_one(self):return self.value
            def one(self):return self.value
        class C:
            def __init__(self):self.calls=[]
            def execute(self,statement,params):
                query=str(statement);self.calls.append(query)
                if 'pg_namespace WHERE' in query:return Result(['public'])
                if 'FROM pg_class' in query:return Result(1)
                return Result(('mikrotik_manager_v2','v2_local',55432,'127.0.0.1'))
        for check, code in [(manage.require_empty,'NONEMPTY_TARGET'),(manage.verify_identity,'DATABASE_IDENTITY_REJECTED')]:
            c=C()
            with self.assertRaisesRegex(manage.Blocked,code):check(c)
            self.assertTrue(all(query.startswith('SELECT') for query in c.calls))

    def test_closed_runtime_cannot_point_to_old_target_or_open_router(self):
        env=dict(V2_DEPLOYMENT_PROFILE=fresh_pilot.PROFILE,V2_API_PORT='18090',
            V2_DATABASE_URL='postgresql+psycopg://v2_fresh_app:'+('a'*64)+'@127.0.0.1:55442/mikrotik_manager_v2_fresh_pilot',
            V2_ROUTER_ONBOARDING_ENABLED='false',V2_CEBECI_API_SSL_ENABLED='false',V2_ROUTER_ONBOARDING_OPERATOR_IDS='')
        fresh_pilot.validate(env, fresh_pilot.ROOT/'app')
        from app.core.pilot_runtime import validate_runtime, validate_scope
        validate_runtime(fresh_pilot.ROOT/'app',env)
        for field,value in [('V2_ROUTER_ONBOARDING_ENABLED','true'),('V2_CEBECI_API_SSL_ENABLED','true'),
            ('V2_DATABASE_URL',env['V2_DATABASE_URL'].replace(':55442/',':55432/')),
            ('V2_DATABASE_URL',env['V2_DATABASE_URL'].replace('v2_fresh_app:','v2_local:')),
            ('V2_API_PORT','18080')]:
            with self.subTest(field=field,value=value),self.assertRaises(RuntimeError):
                validate_scope({**env,field:value})
        with patch.dict(os.environ,env,clear=True):
            from app.adapters.router_api_ssl import ConnectionPolicy
            self.assertFalse(ConnectionPolicy.environment().enabled)
            from app.adapters.demo_subscriptions import PostgresDemoStore
            from sqlalchemy import create_engine
            engine=create_engine(env['V2_DATABASE_URL'])
            PostgresDemoStore(engine)
            engine.dispose()

    def test_schema_and_ledger_mismatch_fail_closed(self):
        class Result:
            def scalar_one(self):return '{}'
        class C:
            def execute(self,*args):return Result()
        with self.assertRaisesRegex(manage.Blocked,'SCHEMA_MISMATCH'):
            manage.verify_schema(C())

    def test_default_commands_never_connect_or_stage(self):
        with patch.object(sys,'argv',['manage.py']),patch.object(manage,'connect',side_effect=AssertionError('connection')):
            self.assertEqual(manage.main(),0)


class OperationGates(unittest.TestCase):
    def test_existing_empty_root_blocks_staging_before_accounts_or_socket(self):
        spec=importlib.util.spec_from_file_location('fresh_stage', HERE/'stage-approved.py')
        stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
        with tempfile.TemporaryDirectory() as directory, patch.object(stage,'ROOT',Path(directory)),patch.object(stage.os,'geteuid',return_value=0),patch.object(stage.socket,'socket') as socket_factory,patch.object(stage.pwd,'getpwnam') as account:
            with self.assertRaisesRegex(manage.Blocked,'TARGET_ROOT_EXISTS'):
                stage.preflight()
            socket_factory.assert_not_called();account.assert_not_called()

    def test_backup_verifies_identity_before_process_and_scrubs_environment(self):
        import types
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'backups').mkdir()
            calls=[]
            def run(argv,**kwargs):
                calls.append((argv,kwargs))
                if argv[0].endswith('/pg_dump'):
                    Path(argv[-1]).write_bytes(b'synthetic-only-archive')
                return types.SimpleNamespace(returncode=0)
            manifest, data, _=manage.check_sources()
            with patch.object(manage,'ROOT',root),patch.object(manage,'verify'),patch.object(manage.subprocess,'run',side_effect=run),patch.dict(os.environ,{'PGHOST':'forbidden','PGPASSWORD':'synthetic-canary'}):
                manage.backup(None,manifest,data)
            self.assertEqual(len(calls),2)
            for argv,kwargs in calls:
                self.assertNotIn('PGPASSWORD',kwargs['env'])
                self.assertNotIn('PGHOST',kwargs['env'])
                self.assertNotIn('synthetic-canary',repr(argv))
            receipt=json.loads(next((root/'backups').glob('*/receipt.json')).read_text())
            self.assertEqual(receipt['restore_drill'],'NOT_PERFORMED')
            self.assertEqual(receipt['dump_sha256'],manage.digest(b'synthetic-only-archive'))
            with patch.object(manage,'verify',side_effect=manage.Blocked('DATABASE_IDENTITY_REJECTED')),patch.object(manage.subprocess,'run') as process:
                with self.assertRaises(manage.Blocked):manage.backup(None,manifest,data)
                process.assert_not_called()


class OfflinePostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bin=Path('/usr/lib/postgresql/16/bin')
        if not (cls.bin/'postgres').exists():
            raise unittest.SkipTest('PostgreSQL 16 offline binaries unavailable')
        cls.temp=tempfile.TemporaryDirectory(prefix='v2-fresh-synthetic-')
        cls.data=Path(cls.temp.name)/'pg'
        r=subprocess.run([str(cls.bin/'initdb'),'-D',str(cls.data),'-U','v2_fresh_owner','--auth=reject','--no-instructions','--locale=C.UTF-8'],capture_output=True,text=True)
        if r.returncode:
            cls.temp.cleanup()
            raise RuntimeError('synthetic offline initdb failed')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def single(self,sql,errors=False):
        sql=re.sub(r'--[^\n]*','',sql).replace('\n',' ')+'\n'
        r=subprocess.run([str(self.bin/'postgres'),'--single','-D',str(self.data),'postgres'],input=sql,capture_output=True,text=True)
        self.assertEqual(r.returncode,0)
        if not errors:self.assertNotIn('ERROR:',r.stderr)
        return r

    def schema(self):
        r=self.single((HERE/'schema.sql').read_text())
        return json.loads(re.search(r'1: schema_json = "(.*)"\t',r.stdout)[1])

    def test_forward_atomic_identity_ledger_and_rollback(self):
        _,manifest,sql=manage.check_sources()
        class Capture:
            def __init__(self):self.statements=[]
            def execute(self,statement,params=None):
                from psycopg import sql
                query=str(statement)
                for key in sorted(params or {},key=len,reverse=True):
                    query=re.sub(':'+re.escape(key)+r'\b',lambda m:sql.Literal(params[key]).as_string(),query)
                self.statements.append(query+';')
                class Result:
                    def scalar_one_or_none(self):return None
                return Result()
        c=Capture()
        payload=FirstAdminInput(username='synthetic-admin',name='Synthetic',email='synthetic@example.invalid',password='synthetic-test-password-2026')
        # Capture the actual runner (only DB responses/identity checks are replaced).
        # Its complete SQL, account/audit helper and grants execute in real PG below.
        with patch.object(manage,'verify_identity'),patch.object(manage,'require_empty'),patch.object(manage,'verify_schema'),patch.object(manage,'verify'),patch.object(manage,'schema_hash',return_value='a'*64):
            manage.migrate(c, *manage.check_sources(), payload, 1000, 'b'*64)
        body='\n'.join(c.statements)
        self.assertLess(body.index('ADD COLUMN account_origin'),body.index('FIRST_ADMIN_CREATE'))
        self.assertLess(body.index('FIRST_ADMIN_CREATE'),body.index("'009_first_local_admin.sql'"))
        self.single('CREATE DATABASE mikrotik_manager_v2_fresh_pilot;')
        # A deliberate error after 009 must roll back every table, identity and ledger.
        r=self.single('BEGIN; SET search_path=public,pg_catalog;'+body+'SELECT 1/0; COMMIT;',errors=True)
        self.assertIn('ERROR:',r.stderr)
        self.assertEqual(self.schema()['schemas'],['public'])
        # Full forward SQL and the production helper's identity/audit/seal writes commit.
        self.single('BEGIN; SET search_path=public,pg_catalog;'+body+'COMMIT;')
        self.assertEqual(self.schema(),json.loads((HERE/'schema.expected.json').read_text()))
        r=self.single("SELECT count(*) AS ledger_count FROM v2_migrations.applied; SELECT first_admin_initialized AS sealed FROM v2_demo.schema_state; SELECT count(*) AS audit_count FROM v2_demo.user_audit; SELECT count(*) AS default_count FROM v2_demo.settings_records WHERE id='default';")
        self.assertIn('ledger_count = "9"',r.stdout)
        self.assertIn('sealed = "t"',r.stdout)
        self.assertIn('audit_count = "1"',r.stdout)
        self.assertIn('default_count = "1"',r.stdout)
        # DDL drift changes the full signature; table-name presence alone is insufficient.
        self.single('ALTER TABLE public.routers ALTER COLUMN name TYPE varchar(121);')
        self.assertNotEqual(self.schema(),json.loads((HERE/'schema.expected.json').read_text()))


if __name__ == '__main__':
    unittest.main()
