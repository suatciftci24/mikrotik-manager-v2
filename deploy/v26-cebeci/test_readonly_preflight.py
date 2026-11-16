"""Synthetic tests only: no VDS, sockets, service control or database connection."""
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tarfile
import tempfile
import unittest
import contextlib
from unittest.mock import Mock,MagicMock,patch

spec=importlib.util.spec_from_file_location('readonly_v26_preflight',Path(__file__).with_name('readonly-preflight.py'))
preflight=importlib.util.module_from_spec(spec);spec.loader.exec_module(preflight)

class ReadonlyPreflightTests(unittest.TestCase):
    def setUp(self):
        preflight.REPORT.clear()

    def test_contract_matches_current_orm_without_invented_schema_names(self):
        from app.models.router_registry import RegisteredRouter,RouterVerification,RouterRegistryAudit
        import hashlib
        tables=(RegisteredRouter.__table__,RouterVerification.__table__,RouterRegistryAudit.__table__)
        self.assertEqual(set(preflight.CONTRACT),{t.name for t in tables})
        for table in tables:
            self.assertIsNone(table.schema)
            expected=preflight.CONTRACT[table.name]
            self.assertEqual(expected['columns'],{c.name:[str(c.type).upper(),c.nullable] for c in table.columns})
            self.assertEqual(expected['indexes'],{i.name:[c.name for c in i.columns] for i in table.indexes})
        model=Path(__file__).resolve().parents[2]/'backend/app/models/router_registry.py'
        self.assertEqual(preflight.MODEL_SHA256,hashlib.sha256(model.read_bytes()).hexdigest())

    def test_env_parser_preserves_literal_secrets_without_execution_or_output(self):
        secret='synthetic-$(touch /never-created)-`id`-#literal'
        raw=('V2_DATABASE_URL="'+secret+'"\nV2_EMPTY=\n# ignored\n').encode()
        with patch('subprocess.run',side_effect=AssertionError('No execution')):
            self.assertEqual(preflight.environment_file(raw)['V2_DATABASE_URL'],secret)
        for raw in (b'export X=value',b'X=a\nX=b',b'X="unterminated',b'X=one two'):
            with self.assertRaises(Exception):preflight.environment_file(raw)

    def test_existing_cookie_only_safe_get_no_redirect_or_login(self):
        user=dict(id='v2-user-11111111-2222-4333-8444-555555555555',revision=2,account_origin='LOCAL',
                  active=True,role_code='ADMIN',bootstrap_closed=True,can_manage_users=True,
                  pilot_identity={'state':'ELIGIBLE','candidate':dict(id='v2-user-11111111-2222-4333-8444-555555555555',revision=2,source='V2_AUTHENTICATED_SESSION')})
        connection=Mock();response=connection.getresponse.return_value
        response.status=200;response.read.return_value=json.dumps(user).encode()
        with patch.object(preflight.http.client,'HTTPConnection',return_value=connection) as client:
            self.assertEqual(preflight.session_identity('a'*43),{'id':user['id'],'revision':2})
            self.assertEqual(connection.request.call_args.args[:2],('GET','/api/v1/auth/me'))
            client.assert_called_once_with('127.0.0.1',18996,timeout=8)
            response.status=302
            with self.assertRaises(preflight.Blocked):preflight.session_identity('a'*43)
            with self.assertRaises(preflight.Blocked):preflight.api_get('/api/v1/auth/login','a'*43)
        for change in ({'account_origin':'DEMO'},{'active':False},{'role_code':'VIEWER'},{'can_manage_users':False},{'revision':3}):
            with patch.object(preflight,'api_get',return_value={**user,**change}):
                with self.assertRaises(preflight.Blocked):preflight.session_identity('a'*43)
        with self.assertRaises(preflight.Blocked):preflight.selection({'V2_V26_CEBECI_READ_ENABLED':'true','V2_V26_CEBECI_OPERATOR_ID':'old-id'}, {'id':user['id'],'revision':2})
        preflight.selection({}, {'id':user['id'],'revision':2})  # Does not grant anything.

    def test_backup_checks_read_only_and_mismatched_or_incomplete_backups_block(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'code.tar';expected={'backend/app/main.py':b'code','frontend/dist/index.html':b'html'}
            with tarfile.open(archive,'w') as stream:
                for name,value in expected.items():
                    item=tarfile.TarInfo(name);item.size=len(value);stream.addfile(item,io.BytesIO(value))
            archive.chmod(0o600)
            with patch.object(preflight,'read_file',wraps=preflight.read_file) as reader:
                preflight.archive_matches(archive,expected,{archive.stat().st_uid})
                self.assertTrue(reader.call_args.kwargs['metadata_only'])
            with self.assertRaises(preflight.Blocked):preflight.archive_matches(archive,{**expected,'missing':b'value'},None)
            with self.assertRaises(preflight.Blocked):preflight.archive_matches(archive,{**expected,'frontend/dist/index.html':b'FAIL'},None)
            archive.chmod(0o644)
            with self.assertRaises(preflight.Blocked):preflight.archive_matches(archive,expected,None)
            self.assertEqual(set(root.iterdir()),{archive})

    def test_dump_list_checks_correct_database_and_user_subscriber_data_without_printing(self):
        toc=b';     dbname: mikrotik_v26_acceptance\n1; 0 1 TABLE DATA v26_acceptance users owner\n2; 0 2 TABLE DATA v26_acceptance subscribers owner\n'
        with patch.object(preflight,'read_file') as reader,patch.object(preflight.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=toc)) as run:
            preflight.dump_valid(Path('/private/dump'),{0})
            self.assertTrue(reader.call_args.kwargs['metadata_only'])
            self.assertEqual(run.call_args.args[0],['/usr/lib/postgresql/16/bin/pg_restore','--list','/private/dump'])
            run.return_value.stdout=toc.replace(b'mikrotik_v26_acceptance',b'other_db')
            with self.assertRaises(preflight.Blocked):preflight.dump_valid(Path('/private/dump'),{0})

    def test_source_route_is_kernel_metadata_only(self):
        replies=[SimpleNamespace(returncode=0,stdout=b'[{"addr_info":[{"local":"10.250.0.1"}]}]'),
                 SimpleNamespace(returncode=0,stdout=b'[{"dev":"synthetic-ipsec","from":"10.250.0.1"}]')]
        with patch.object(preflight.shutil,'which',return_value='/usr/sbin/ip'),patch.object(preflight.subprocess,'run',side_effect=replies) as run:
            preflight.source_route()
            self.assertEqual(run.call_args_list[1].args[0],['/usr/sbin/ip','-j','-4','route','get','10.250.0.19','from','10.250.0.1'])

    def test_subprocess_secret_on_stdin_only_and_failures_never_export_stderr(self):
        identity={'id':'synthetic','revision':1};values={'V2_DATABASE_URL':'SYNTHETIC_SECRET_CANARY'}
        with patch.object(preflight.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'SYNTHETIC_SECRET_CANARY')) as run:
            with self.assertRaises(preflight.Blocked) as error:preflight.database(values,identity,'/p/python',1000,1000)
            self.assertNotIn('CANARY',str(error.exception))
            self.assertNotIn('CANARY',str(run.call_args.args))
            self.assertIn(b'CANARY',run.call_args.kwargs['input'])
            self.assertNotIn('V2_DATABASE_URL',run.call_args.kwargs['env'])
        preflight.check('redaction',lambda:(_ for _ in ()).throw(ValueError('CANARY')))
        self.assertEqual(preflight.REPORT['redaction'],'BLOCKED:CHECK_UNAVAILABLE')

    def test_db_program_is_readonly_and_checks_catalog_existence_separately_from_visibility(self):
        import ast
        tree=ast.parse(preflight.DB_INSPECT)
        queries=[v.value for v in ast.walk(tree) if isinstance(v,ast.Constant) and isinstance(v.value,str)
                 and v.value.startswith(('SELECT ','SET ','INSERT ','UPDATE ','DELETE ','CREATE ','ALTER '))]
        self.assertTrue(queries)
        self.assertFalse(any(q.startswith(('INSERT ','UPDATE ','DELETE ','CREATE ','ALTER ')) for q in queries))
        self.assertIn('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY',queries)
        self.assertIn('tx.rollback()',preflight.DB_INSPECT)
        self.assertIn('pg_class',preflight.DB_INSPECT);self.assertIn('to_regclass',preflight.DB_INSPECT)
        self.assertNotIn('password_hash',preflight.DB_INSPECT)
        self.assertNotIn('DROP ',preflight.DB_INSPECT)
        self.assertNotIn('login',preflight.DB_INSPECT)

    def test_database_program_distinguishes_absent_hidden_and_compatible_tables(self):
        from sqlalchemy.engine import make_url
        identity={'id':'synthetic-admin','revision':2}
        request=dict(url='postgresql+psycopg://v26_acceptance:synthetic-password-only-123@127.0.0.1:55433/mikrotik_v26_acceptance',identity=identity,contract=preflight.CONTRACT)
        for mode in ('absent','hidden','rights','compatible'):
            engine=MagicMock();connection=engine.connect.return_value.__enter__.return_value;inspector=Mock()
            def execute(statement,params=None):
                sql=str(statement);reply=Mock()
                if 'SELECT current_database(),' in sql:reply.one.return_value=('mikrotik_v26_acceptance','v26_acceptance',55433)
                elif 'SELECT marker FROM' in sql:reply.scalar_one.return_value='mikrotik-manager-v2-synthetic-only'
                elif 'SELECT id,revision' in sql:reply.one_or_none.return_value=(identity['id'],2,'ADMIN',True,'LOCAL')
                elif 'WHERE t.relname=' in sql:reply.scalars.return_value.all.return_value=[] if mode=='absent' else ['public']
                elif 'WHERE t.oid=to_regclass' in sql:reply.scalar_one_or_none.return_value=None if mode in ('absent','hidden') else 'public'
                elif 'has_database_privilege' in sql:reply.one.return_value=(True,True,mode!='rights',True,True)
                return reply
            connection.execute.side_effect=execute
            inspector.get_columns.side_effect=lambda name,**kw:[dict(name=k,type=v[0],nullable=v[1]) for k,v in preflight.CONTRACT[name]['columns'].items()]
            inspector.get_pk_constraint.return_value={'constrained_columns':['id']}
            inspector.get_indexes.side_effect=lambda name,**kw:[dict(name=k,column_names=v) for k,v in preflight.CONTRACT[name]['indexes'].items()]
            inspector.get_unique_constraints.return_value=[{'column_names':['management_address','port']}]
            output=io.StringIO()
            with patch('sys.stdin',io.StringIO(json.dumps(request))),patch('sqlalchemy.create_engine',return_value=engine),patch('sqlalchemy.inspect',return_value=inspector),contextlib.redirect_stdout(output):
                exec(compile(preflight.DB_INSPECT,'synthetic-readonly-db-check','exec'),{})
            result=json.loads(output.getvalue())
            self.assertEqual(result['database'],'PASS')
            expected={'absent':'BLOCKED:TABLE_ABSENT','hidden':'BLOCKED:TABLE_SHADOWED_OR_NOT_RESOLVABLE','rights':'BLOCKED:CONNECT_USAGE_SELECT_INSERT_UPDATE_REQUIRED','compatible':'PASS'}[mode]
            for name in preflight.TABLES:self.assertEqual(result[name],expected)
            connection.begin.return_value.rollback.assert_called_once()
            engine.dispose.assert_called_once()

    def test_private_files_reject_symlink_hardlink_and_do_not_change_permissions(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);secret=root/'private';secret.write_bytes(b'SYNTHETIC_SECRET');secret.chmod(0o600)
            link=root/'link';link.symlink_to(secret)
            with self.assertRaises(preflight.Blocked):preflight.read_file(link,private=True)
            link.unlink();os.link(secret,link)
            with self.assertRaises(preflight.Blocked):preflight.read_file(secret,private=True)
            link.unlink()
            self.assertEqual(preflight.read_file(secret,private=True),b'SYNTHETIC_SECRET')
            self.assertEqual(secret.stat().st_mode&0o777,0o600)

    def test_https_frontend_and_api_must_match_same_running_source(self):
        index=b'<script src="/assets/main.js"></script><link href="/assets/main.css">'
        files={'frontend/dist/index.html':index,'frontend/dist/assets/main.js':b'js','frontend/dist/assets/main.css':b'css'}
        identity=dict(repo_id='same',build_id='same',api_port=18996,runtime_profile='v26-isolated-acceptance')
        responses={'/':index,'/api/ready':json.dumps(identity).encode(),'/assets/main.js':b'js','/assets/main.css':b'css'}
        with patch.object(preflight,'https_get',side_effect=lambda path:responses[path]),patch.object(preflight,'api_get',return_value=identity):
            preflight.frontend_live(files)
            responses['/assets/main.css']=b'WRONG'
            with self.assertRaisesRegex(preflight.Blocked,'ASSET_MISMATCH'):preflight.frontend_live(files)
        self.assertIsNone(preflight.NoRedirect().redirect_request(None,None,None,None,None,None))
        with self.assertRaises(preflight.Blocked):preflight.https_get('https://other-host/secret')

    def test_only_loaded_unchanged_running_unit_metadata_is_accepted(self):
        data=b'ActiveState=active\nSubState=running\nNeedDaemonReload=no\n'
        with patch.object(preflight.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=data)) as run:
            self.assertEqual(preflight.unit('mikrotik-v26-api.service')['NeedDaemonReload'],'no')
            self.assertEqual(run.call_args.args[0][:3],['/usr/bin/systemctl','show','mikrotik-v26-api.service'])
            run.return_value.stdout=data.replace(b'Reload=no',b'Reload=yes')
            with self.assertRaisesRegex(preflight.Blocked,'DISK_AND_LOADED'):preflight.unit('mikrotik-v26-api.service')

    def test_private_material_is_file_based_offline_and_scope_pinned(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pilot=root/'.local/cebeci-pilot'
            for path in (pilot,pilot/'trust',pilot/'secrets'):path.mkdir(mode=0o700,parents=True,exist_ok=True)
            for name,value in (('secrets/username','v2-cebeci-ro'),('secrets/password','SYNTHETIC_CANARY'),('trust/ca.pem','SYNTHETIC_CA')):
                path=pilot/name;path.write_text(value);path.chmod(0o600)
            with patch.object(preflight,'ROOT',root),patch.object(preflight.ssl,'create_default_context') as context:
                preflight.private_material(os.getuid(),{})
                context.assert_called_once_with(cadata='SYNTHETIC_CA')
                with self.assertRaisesRegex(preflight.Blocked,'SCOPE_OVERRIDE'):
                    preflight.private_material(os.getuid(),{'V2_CEBECI_API_SSL_HOST':'10.250.0.18'})
                (pilot/'secrets/password').chmod(0o644)
                with self.assertRaises(preflight.Blocked):preflight.private_material(os.getuid(),{})
