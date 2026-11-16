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
            with patch.object(preflight,'regular_file',wraps=preflight.regular_file) as reader:
                preflight.archive_matches(archive,expected,{archive.stat().st_uid})
                self.assertTrue(reader.call_args.kwargs['private'])
            with self.assertRaises(preflight.Blocked):preflight.archive_matches(archive,{**expected,'missing':b'value'},None)
            with self.assertRaises(preflight.Blocked):preflight.archive_matches(archive,{**expected,'frontend/dist/index.html':b'FAIL'},None)
            archive.chmod(0o644)
            with self.assertRaises(preflight.Blocked):preflight.archive_matches(archive,expected,None)
            self.assertEqual(set(root.iterdir()),{archive})

    def test_dump_list_checks_correct_database_and_user_subscriber_data_without_printing(self):
        toc=b';     dbname: mikrotik_v26_acceptance\n1; 0 1 TABLE DATA v26_acceptance users owner\n2; 0 2 TABLE DATA v26_acceptance subscribers owner\n'
        import os,fcntl
        with tempfile.TemporaryDirectory() as temp:
            dump=Path(temp)/'dump';dump.write_bytes(b'SYNTHETIC_DUMP');dump.chmod(0o600)
            def read_fd(args,**kwargs):
                fd=kwargs['pass_fds'][0]
                self.assertEqual(args[1:],['--list','/proc/self/fd/'+str(fd)])
                self.assertEqual(fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE,os.O_RDONLY)
                self.assertEqual(os.read(fd,32),b'SYNTHETIC_DUMP')
                return SimpleNamespace(returncode=0,stdout=toc)
            with patch.object(preflight,'trusted_system_path',side_effect=lambda p:p),patch.object(preflight,'run_tool',side_effect=read_fd):
                preflight.dump_valid(dump,{os.getuid()})
            with patch.object(preflight,'trusted_system_path',side_effect=lambda p:p),patch.object(preflight,'run_tool',return_value=SimpleNamespace(returncode=0,stdout=toc.replace(b'mikrotik_v26_acceptance',b'other_db'))):
                with self.assertRaises(preflight.Blocked):preflight.dump_valid(dump,{os.getuid()})

    def test_source_route_is_kernel_metadata_only(self):
        replies=[SimpleNamespace(returncode=0,stdout=b'[{"addr_info":[{"local":"10.250.0.1"}]}]'),
                 SimpleNamespace(returncode=0,stdout=b'[{"dev":"synthetic-ipsec","from":"10.250.0.1"}]')]
        with patch.object(preflight,'trusted_system_path',side_effect=lambda p:p),patch.object(preflight.shutil,'which',return_value='/usr/sbin/ip'),patch.object(preflight,'run_tool',side_effect=replies) as run:
            preflight.source_route()
            self.assertEqual(run.call_args_list[1].args[0],['/usr/sbin/ip','-j','-4','route','get','10.250.0.19','from','10.250.0.1'])

    def test_subprocess_secret_on_stdin_only_and_failures_never_export_stderr(self):
        identity={'id':'synthetic','revision':1};values={'V2_DATABASE_URL':'SYNTHETIC_SECRET_CANARY'}
        with patch.object(preflight,'trusted_system_path',return_value='/usr/bin/python3'),patch.object(preflight,'run_tool',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'SYNTHETIC_SECRET_CANARY')) as run:
            with self.assertRaises(preflight.Blocked) as error:preflight.database(values,identity,1000,1000)
            self.assertNotIn('CANARY',str(error.exception))
            self.assertNotIn('CANARY',str(run.call_args.args))
            self.assertIn(b'CANARY',run.call_args.kwargs['input'])
            self.assertNotIn('V2_DATABASE_URL',run.call_args.kwargs['env'])
            self.assertEqual(run.call_args.args[0][:4],['/usr/bin/python3','-I','-S','-B'])
        preflight.check('redaction',lambda:(_ for _ in ()).throw(ValueError('CANARY')))
        self.assertEqual(preflight.REPORT['redaction'],'BLOCKED:CHECK_UNAVAILABLE')

    def test_db_program_is_readonly_and_checks_catalog_existence_separately_from_visibility(self):
        import ast
        tree=ast.parse(preflight.DB_INSPECT)
        queries=[v.value for v in ast.walk(tree) if isinstance(v,ast.Constant) and isinstance(v.value,str)
                 and v.value.startswith(('SELECT ','SET ','SHOW ','BEGIN ','ROLLBACK','INSERT ','UPDATE ','DELETE ','CREATE ','ALTER '))]
        self.assertTrue(queries)
        self.assertFalse(any(q.startswith(('INSERT ','UPDATE ','DELETE ','CREATE ','ALTER ')) for q in queries))
        self.assertIn('BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY',queries)
        self.assertIn("query('ROLLBACK')",preflight.DB_INSPECT)
        self.assertFalse(any(isinstance(v,ast.Assert) for v in ast.walk(tree)))
        self.assertIn('pg_class',preflight.DB_INSPECT);self.assertIn('to_regclass',preflight.DB_INSPECT)
        self.assertNotIn('password_hash',preflight.DB_INSPECT)
        self.assertNotIn('DROP ',preflight.DB_INSPECT)
        self.assertNotIn('login',preflight.DB_INSPECT)

    def test_database_program_distinguishes_absent_hidden_and_compatible_tables(self):
        namespace={'__name__':'synthetic_no_network'}
        exec(compile(preflight.DB_INSPECT,'synthetic-db-helpers','exec'),namespace)
        identity={'id':'synthetic-admin','revision':2};request={'identity':identity,'contract':preflight.CONTRACT}
        for mode in ('absent','hidden','rights','compatible','not_readonly'):
            calls=[]
            def query(sql,params=()):
                calls.append(sql)
                if sql=='SHOW transaction_read_only':return [['off' if mode=='not_readonly' else 'on']]
                if 'SELECT pg_catalog.current_database(),' in sql:return [['mikrotik_v26_acceptance','v26_acceptance','55433']]
                if 'SELECT relkind FROM' in sql:return [['r']]
                if 'SELECT marker FROM' in sql:return [['mikrotik-manager-v2-synthetic-only']]
                if 'SELECT id,revision' in sql:return [[identity['id'],'2','ADMIN','t','LOCAL']]
                if 'WHERE t.relname=' in sql:return [] if mode=='absent' else [['public']]
                if 'WHERE t.oid=pg_catalog.to_regclass' in sql:return [] if mode in ('absent','hidden') else [['public']]
                if 'has_database_privilege' in sql:return [['t','t','f' if mode=='rights' else 't','t','t']]
                if 'SELECT attname,' in sql:
                    contract=preflight.CONTRACT[params[0].split('.',1)[1]]
                    return [[name,values[0],'t' if values[1] else 'f'] for name,values in contract['columns'].items()]
                if 'SELECT ci.relname,' in sql:
                    contract=preflight.CONTRACT[params[0].split('.',1)[1]]
                    rows=[[name,json.dumps(columns),'f','f'] for name,columns in contract['indexes'].items()]
                    rows.append(['pk','["id"]','t','t'])
                    if contract['unique']:rows.append(['endpoint',json.dumps(contract['unique']),'f','t'])
                    return rows
                return []
            result=namespace['inspect_database'](request,query)
            if mode=='not_readonly':self.assertEqual(result['database'],'BLOCKED:READONLY_DATABASE_INSPECTION_FAILED')
            else:
                self.assertEqual(result['database'],'PASS')
                expected={'absent':'BLOCKED:TABLE_ABSENT','hidden':'BLOCKED:TABLE_SHADOWED_OR_NOT_RESOLVABLE','rights':'BLOCKED:CONNECT_USAGE_SELECT_INSERT_UPDATE_REQUIRED','compatible':'PASS'}[mode]
                for name in preflight.TABLES:self.assertEqual(result[name],expected)
            self.assertEqual(calls[-1],'ROLLBACK')

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
        with patch.object(preflight,'trusted_system_path',side_effect=lambda p:p),patch.object(preflight,'run_tool',return_value=SimpleNamespace(returncode=0,stdout=data)) as run:
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
            with patch.object(preflight,'ROOT',root),patch.object(preflight,'tls_context') as context:
                preflight.private_material(os.getuid(),{})
                context.assert_called_once_with('SYNTHETIC_CA')
                with self.assertRaisesRegex(preflight.Blocked,'SCOPE_OVERRIDE'):
                    preflight.private_material(os.getuid(),{'V2_CEBECI_API_SSL_HOST':'10.250.0.18'})
                (pilot/'secrets/password').chmod(0o644)
                with self.assertRaises(preflight.Blocked):preflight.private_material(os.getuid(),{})

    def test_tls_ignores_keylog_and_external_ca_environment_without_writing(self):
        import os,ssl
        with tempfile.TemporaryDirectory() as temp:
            keylog=Path(temp)/'must-not-exist'
            with patch.dict(os.environ,{'SSLKEYLOGFILE':str(keylog),'SSL_CERT_FILE':'/no-such-custom-ca','SSL_CERT_DIR':'/no-such-ca-dir'}):
                context=preflight.tls_context()
            self.assertIsNone(context.keylog_filename)
            self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            self.assertGreaterEqual(context.minimum_version,ssl.TLSVersion.TLSv1_2)
            self.assertFalse(keylog.exists())
        with patch.object(preflight.http.client,'HTTPConnection') as client:
            with self.assertRaisesRegex(preflight.Blocked,'SESSION_DESTINATION'):
                preflight.api_get('/api/health','a'*43)
            client.assert_not_called()

    def test_system_child_has_no_site_imports_and_output_timeout_are_bounded(self):
        import sys
        result=preflight.run_tool([sys.executable,'-I','-S','-B','-c',"import sys;sys.stderr.write('SYNTHETIC_SECRET');print(len(sys.stdin.buffer.read()))"],
            timeout=5,env=preflight.TOOL_ENV,input=b'SYNTHETIC_SECRET',max_output=32)
        self.assertEqual(result.stdout.strip(),b'16')
        self.assertEqual(result.stderr,b'')
        with self.assertRaisesRegex(preflight.Blocked,'OUTPUT_LIMIT'):
            preflight.run_tool([sys.executable,'-I','-S','-B','-c',"print('x'*10000)"],timeout=5,env=preflight.TOOL_ENV,max_output=32)
        with self.assertRaisesRegex(preflight.Blocked,'TIMEOUT'):
            preflight.run_tool([sys.executable,'-I','-S','-B','-c','import time;time.sleep(10)'],timeout=.1,env=preflight.TOOL_ENV)

    def test_libpq_fixed_target_readonly_parameters_and_c_resource_cleanup(self):
        namespace={'__name__':'synthetic_no_network'}
        exec(compile(preflight.DB_INSPECT,'synthetic-libpq','exec'),namespace)
        url='postgresql+psycopg://v26_acceptance:synthetic-password-only-123@127.0.0.1:55433/mikrotik_v26_acceptance'
        with patch.object(namespace['ctypes'],'CDLL',side_effect=AssertionError('No foreign IO')) as library:
            for bad in (url.replace('127.0.0.1','remote'),url+'?host=/other/socket',url+'#fragment',url.replace('55433','5432')):
                with self.assertRaises(RuntimeError):namespace['LibPQ'](bad)
            library.assert_not_called()
        library=Mock();library.PQstatus.return_value=0;library.PQconnectdbParams.return_value=123
        def connect(keys,values,expand):
            config={};i=0
            while keys[i] is not None:config[keys[i].decode()]=values[i].decode();i+=1
            self.assertEqual(config['hostaddr'],'127.0.0.1');self.assertEqual(config['port'],'55433')
            self.assertIn('default_transaction_read_only=on',config['options'])
            self.assertEqual(config['sslmode'],'disable');self.assertEqual(config['gssencmode'],'disable')
            self.assertEqual(config['passfile'],'/dev/null')
            self.assertEqual(expand,0)
            return 123
        library.PQconnectdbParams.side_effect=connect
        namespace['trusted']=lambda path:'/trusted/libpq.so.5'
        with patch.object(namespace['ctypes'],'CDLL',return_value=library),patch.dict(namespace,{'Path':Mock(return_value=Mock(exists=lambda:True))}):
            driver=namespace['LibPQ'](url)
        library.PQexecParams.return_value=456;library.PQresultStatus.return_value=2
        library.PQntuples.return_value=1;library.PQnfields.return_value=1
        library.PQgetisnull.return_value=0;library.PQgetvalue.return_value=b'public'
        self.assertEqual(driver.query('SELECT $1',('synthetic',)),[['public']])
        library.PQclear.assert_called_once_with(456)
        library.PQresultStatus.return_value=7
        with self.assertRaisesRegex(RuntimeError,'^DATABASE_QUERY_REJECTED$'):driver.query('SELECT $1',('private-value',))
        driver.close();library.PQfinish.assert_called_once_with(123)

    def test_anchored_read_survives_parent_path_replacement_without_following_link(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);parent=base/'nested';other=base/'other';parent.mkdir();other.mkdir()
            (parent/'data').write_bytes(b'original');(other/'data').write_bytes(b'wrong-target')
            actual_open=os.open;changed=False
            def replace_parent(path,*args,**kwargs):
                nonlocal changed
                fd=actual_open(path,*args,**kwargs)
                if path=='nested' and not changed:
                    changed=True;parent.rename(base/'previous');parent.symlink_to(other,target_is_directory=True)
                return fd
            with patch.object(preflight.os,'open',side_effect=replace_parent):
                self.assertEqual(preflight.read_file(parent/'data'),b'original')
            with self.assertRaises(preflight.Blocked):preflight.read_file(parent/'data')

    def test_archive_extended_metadata_is_bounded_before_payload_processing(self):
        item=preflight.BoundedTarInfo('pax');item.type=tarfile.XHDTYPE;item.size=65537
        with self.assertRaisesRegex(preflight.Blocked,'METADATA_LIMIT'):item._proc_member(Mock())
        item.type=tarfile.GNUTYPE_SPARSE;item.size=1
        with self.assertRaisesRegex(preflight.Blocked,'TYPE_REJECTED'):item._proc_member(Mock())
