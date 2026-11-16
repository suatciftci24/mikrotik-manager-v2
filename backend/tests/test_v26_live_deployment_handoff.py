"""Offline deployment/rollback simulation; no SSH, DB, or service commands."""
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('live_worker',ROOT/'tools/deploy_v26_remote.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
TARGET = '69279d22c0f31ef3624a2676ce4edd9eb1863bf7'


class LiveDeploymentHandoff(TestCase):
    def test_stash_pin_rejects_missing_or_ambiguous_label(self):
        def run(*args,**kwargs):return 'a'*40+' On main: '+worker.STASH
        lines,oid=worker.stash_pin(run)
        self.assertEqual(oid,'a'*40)
        for output in ['', run()+'\n'+run()]:
            with self.assertRaisesRegex(RuntimeError,'STASH_LABEL_REJECTED'):
                worker.stash_pin(lambda *a,**kw:output)

    def test_tree_hash_rejects_symlinks_and_detects_asset_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            (path/'asset').write_text('old')
            before=worker.tree_hash(path)
            (path/'asset').write_text('new')
            self.assertNotEqual(before,worker.tree_hash(path))
            (path/'link').symlink_to(path/'asset')
            with self.assertRaisesRegex(RuntimeError,'DIST_SYMLINK_REJECTED'):worker.tree_hash(path)

    def test_non_v26_service_is_never_selected_or_restarted(self):
        calls=[]
        def run(args,**kwargs):
            calls.append(args)
            return 'v1.service loaded active running V1\npostgresql.service loaded active running PostgreSQL'
        with self.assertRaisesRegex(RuntimeError,'SINGLE_V26_API_SERVICE_REQUIRED'):worker.services(run)
        self.assertEqual(len(calls),1)

    def test_http_identity_is_fail_closed(self):
        for profile in [{},dict(service='mikrotik-manager-v2',runtime_profile='v25',api_version='v1',api_port=18996)]:
            with patch.object(worker,'request',return_value=json.dumps(profile).encode()),self.assertRaises(RuntimeError):
                worker.ready(object())

    def simulate(self, fail_panel=False, compatible=True, drift=False, vite=False):
        with tempfile.TemporaryDirectory() as temp:
            app=Path(temp)/'app'
            (app/'.git').mkdir(parents=True)
            (app/'backend').mkdir()
            dist=app/'frontend/dist'
            (dist/'assets').mkdir(parents=True)
            (dist/'index.html').write_text('<html>old</html>')
            (dist/'assets/old.js').write_text('old')
            source=Path(temp)/'dist'
            (source/'assets').mkdir(parents=True)
            (source/'index.html').write_text('<html><script src="/assets/new.js"></script></html>')
            (source/'assets/new.js').write_text('new')
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w') as archive:archive.add(source,arcname='dist')
            raw=buffer.getvalue()
            state={'head':worker.BASELINE}
            calls=[]
            class Failure(RuntimeError):pass
            def run(args,*,stage,**kwargs):
                calls.append((args,stage,kwargs))
                if args[0]=='git':
                    command=args[3:]
                    if command[0]=='rev-parse':return TARGET if command[1]==TARGET+'^{commit}' else state['head']
                    if command[0]=='status':return ''
                    if command[0]=='stash':return 'a'*40+' On main: '+worker.STASH
                    if command[0]=='merge':state['head']=TARGET
                    if command[0]=='switch':state['head']=worker.BASELINE
                if stage=='LIVE_ADMIN_COUNT':return '1'
                if stage=='SERVICE_HEALTH':return 'active'
                return ''
            def inject(source,namespace):
                namespace.update(run=run,CommandFailure=Failure,
                    live_catalog=lambda:dict(columns=[{}] if compatible else None,constraints=None,indexes=None),
                    snapshot=lambda *a,**kw:{'users':'unchanged'},
                    assert_preserved=lambda before,after:self.assertEqual(before,after))
            def request(opener,path,body=None):
                if path=='/':return (dist/'index.html').read_bytes()
                if path.startswith('/assets/'):return (dist/path.lstrip('/')).read_bytes()
                raise AssertionError(path)
            def admin(*args,**kwargs):
                if kwargs.get('panel') and fail_panel:
                    if drift:(dist/'assets/new.js').write_text('concurrent change')
                    raise RuntimeError('PANEL_TEST_FAILURE')
            output=io.StringIO()
            patches=dict(APP=app,TARGET=TARGET,DIST_B64=base64.b64encode(raw).decode(),
                DIST_SHA=hashlib.sha256(raw).hexdigest(),ADMIN={'username':'fixture','password':'private-fixture'},
                MIGRATION_SQL='BEGIN; SELECT 1; COMMIT;',HELPER_SOURCE='fixture only')
            with patch.multiple(worker,create=True,**patches), \
                 patch.object(worker,'exec',side_effect=inject,create=True), \
                 patch.object(worker,'services',return_value=[('mikrotik-v26-api.service',True)]), \
                 patch.object(worker,'verified_webroot',return_value={'mode':'vite-dev' if vite else 'static-dist'}), \
                 patch.object(worker,'evidence',return_value=('fixture-proof','fixture-backup-hash')), \
                 patch.object(worker,'digest',side_effect=lambda path:'fixture-backup-hash' if path==worker.BACKUP else hashlib.sha256(path.read_bytes()).hexdigest()), \
                 patch.object(worker,'client'),patch.object(worker,'ready'), \
                 patch.object(worker,'admin_check',side_effect=admin),patch.object(worker,'request',side_effect=request), \
                 patch.object(worker.signal,'signal'),redirect_stdout(output):
                code=worker.main()
            report=json.loads(output.getvalue())
            self.assertNotIn('private-fixture',output.getvalue())
            self.assertFalse(report['db_restore_performed'])
            if vite:
                self.assertEqual(state['head'],worker.BASELINE)
                self.assertFalse(any(stage in ('LIVE_011_APPLY','CODE_FAST_FORWARD','V26_RESTART') for args,stage,kw in calls))
                return code,report
            self.assertEqual(state['head'],worker.BASELINE if fail_panel and not drift else TARGET)
            restarts=[args[-1] for args,stage,kw in calls if 'RESTART' in stage]
            self.assertTrue(restarts and all(unit=='mikrotik-v26-api.service' for unit in restarts))
            if compatible:
                validate=[kw['sql'] for args,stage,kw in calls if stage=='LIVE_011_VALIDATE']
                self.assertEqual(len(validate),1)
                self.assertIn('BEGIN READ ONLY;',validate[0])
                self.assertFalse(any(stage=='LIVE_011_APPLY' for _,stage,_ in calls))
            else:self.assertEqual(sum(stage=='LIVE_011_APPLY' for _,stage,_ in calls),1)
            return code,report

    def test_success_preserves_stash_and_uses_only_v26_restart(self):
        code,report=self.simulate()
        self.assertEqual(code,0)
        self.assertEqual(report['status'],'PASS')
        self.assertEqual(report['migration'],'COMPATIBLE_NOOP')

    def test_panel_failure_rolls_back_code_and_dist_without_restoring_database(self):
        code,report=self.simulate(fail_panel=True)
        self.assertEqual(code,1)
        self.assertEqual(report['rollback'],'CODE_VERIFIED')
        self.assertEqual(report['status'],'BLOCKED')
        self.assertEqual(report['live_commit'],worker.BASELINE)

    def test_missing_catalog_is_the_only_path_to_explicit_011_apply(self):
        code,report=self.simulate(compatible=False)
        self.assertEqual(code,0)
        self.assertEqual(report['migration'],'APPLIED_011')

    def test_rollback_refuses_concurrent_dist_changes_and_reports_actual_head(self):
        code,report=self.simulate(fail_panel=True,drift=True)
        self.assertEqual(code,1)
        self.assertEqual(report['rollback'],'BLOCKED_REQUIRES_REVIEW')
        self.assertEqual(report['live_commit'],TARGET)
        self.assertFalse(report['db_restore_performed'])

    def test_acceptance_evidence_must_pin_backup_hash_and_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            backup=root/'database.dump'
            backup.write_bytes(b'fixture only')
            path=root/'result.json'
            value=dict(status='PASS',source_commit=TARGET,vds_commit=worker.BASELINE,
                       migration_runs=2,package_schema_match=True,existing_tables_preserved=17,
                       active_admins=1,backup=str(backup),backup_sha256=worker.digest(backup),
                       migration_sha256=hashlib.sha256(b'fixture migration').hexdigest())
            path.write_text(json.dumps(value))
            with patch.multiple(worker,create=True,TARGET=TARGET,MIGRATION_SQL='fixture migration',BACKUP=backup), \
                 patch.object(Path,'glob',return_value=[path]):
                self.assertEqual(worker.evidence()[0],str(path))
                backup.write_bytes(b'changed fixture')
                with self.assertRaisesRegex(RuntimeError,'ACCEPTANCE_EVIDENCE_MISMATCH'):worker.evidence()

    def test_office_reuses_only_pinned_hash_verified_build_artifact(self):
        spec=importlib.util.spec_from_file_location('office_deploy',ROOT/'tools/deploy-v26-office.py')
        office=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(office)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=root/'.local/v26-release-dry-run/fixture'
            folder.mkdir(parents=True,mode=0o700)
            (folder/'source.tar').write_bytes(b'source fixture')
            (folder/'frontend-dist.tar').write_bytes(b'dist fixture')
            manifest=dict(commit=TARGET,build_acceptance='PASS',
                          source_sha256=hashlib.sha256(b'source fixture').hexdigest(),
                          frontend_dist_sha256=hashlib.sha256(b'dist fixture').hexdigest(),
                          migration_sha256=hashlib.sha256(b'migration fixture').hexdigest())
            (folder/'manifest.json').write_text(json.dumps(manifest))
            with patch.object(office,'ROOT',root),patch.object(office,'source',return_value='migration fixture'):
                self.assertEqual(office.build_artifact()['artifact_directory'],str(folder))
                (folder/'frontend-dist.tar').write_bytes(b'corrupt fixture')
                with self.assertRaisesRegex(RuntimeError,'LOCAL_ARTIFACT_HASH_REJECTED'):office.build_artifact()

    def test_panel_acceptance_rejects_http_200_error_body(self):
        calls=[]
        def request(opener,path,body=None):
            calls.append((path,body))
            if path in ('/api/v1/auth/login','/api/v1/auth/me'):
                return json.dumps(dict(id='fixture',role_code='ADMIN')).encode()
            if path.endswith('/summary'):
                return json.dumps(dict(summary=dict(router_count=1,subscribers_total=2))).encode()
            return b'{"detail":"failed despite HTTP 200"}'
        with patch.object(worker,'ADMIN',{'username':'fixture','password':'fixture'},create=True), \
             patch.object(worker,'request',side_effect=request),self.assertRaisesRegex(RuntimeError,'WORKSPACE_CONTRACT_REJECTED'):
            worker.admin_check(object(),panel=True)
        self.assertEqual(calls[-1][0],'/api/v1/auth/logout')
        self.assertTrue(all(body is None or path.startswith('/api/v1/auth/') for path,body in calls))

    def service_fixture(self):
        api=str(worker.APP/'.venv/bin/python')+' -m uvicorn app.main:app --host 127.0.0.1 --port 18996'
        web='/usr/bin/npm run dev -- --host 127.0.0.1 --port 15173 --strictPort'
        return api,web

    def structured_exec(self,command):
        return '{ path='+command.split()[0]+' ; argv[]='+command+' ; ignore_errors=no ; start_time=[Mon 2026-11-16 10:00:00 +03] ; stop_time=[n/a] ; pid=123 ; code=(null) ; status=0/0 }'

    def test_exact_confirmed_api_and_npm_web_exec_are_accepted(self):
        api,web=self.service_fixture()
        for command,cwd,is_api in [(api,str(worker.APP),True),(web,str(worker.APP/'frontend'),False)]:
            for value in [command,self.structured_exec(command)]:
                with self.subTest(value=value):
                    self.assertEqual(worker.service_role(cwd,value,'mikadmin','mikadmin'),is_api)

    def test_service_exec_rejects_command_path_argv_or_metadata_bypass(self):
        api,web=self.service_fixture()
        invalid=[api+' --reload',api.replace('127.0.0.1','0.0.0.0'),api.replace('18996','8000'),
                 api.replace('app.main:app','other:app'),api.replace('.venv/bin/python','backend/venv/bin/python'),
                 self.structured_exec(api).replace('path='+api.split()[0],'path=/usr/bin/python'),
                 self.structured_exec(api)+' '+self.structured_exec(web),
                 self.structured_exec(api).replace('ignore_errors=no','ignore_errors=yes'),
                 self.structured_exec(api).replace('pid=123','argv[]=/bin/sh'),
                 api+'; /bin/sh',api+'\n/bin/sh']
        for command in invalid:
            with self.subTest(command=command),self.assertRaises(RuntimeError):
                worker.service_role(str(worker.APP),command,'mikadmin','mikadmin')
        for command in [web.replace('/usr/bin/npm','/usr/local/bin/npm'),web.replace('15173','5173'),
                        web.replace('--strictPort',''),web.replace('127.0.0.1','0.0.0.0'),web+' --reload']:
            with self.subTest(command=command),self.assertRaises(RuntimeError):
                worker.service_role(str(worker.APP/'frontend'),command,'mikadmin','mikadmin')
        for user,group in [('root','mikadmin'),('mikadmin','root'),('mikadmin','')]:
            with self.subTest(user=user,group=group),self.assertRaisesRegex(RuntimeError,'SERVICE_USER_GROUP_REJECTED'):
                worker.service_role(str(worker.APP),api,user,group)
        with self.assertRaises(RuntimeError):worker.service_role(str(worker.APP/'backend'),api,'mikadmin','mikadmin')
        with self.assertRaises(RuntimeError):worker.service_role(str(worker.APP),web,'mikadmin','mikadmin')

    def test_service_inventory_classifies_web_by_command_even_with_shared_environment(self):
        from types import SimpleNamespace
        api,web=self.service_fixture()
        properties={
            'mikrotik-v26-api.service':dict(WorkingDirectory=str(worker.APP),ExecStart=self.structured_exec(api),User='mikadmin',Group='mikadmin',MainPID='101'),
            'mikrotik-v26-web.service':dict(WorkingDirectory=str(worker.APP/'frontend'),ExecStart=self.structured_exec(web),User='mikadmin',Group='mikadmin',MainPID='102'),
        }
        def run(args,**kw):
            if args[1]=='list-units':return '\n'.join(name+' loaded active running V26' for name in properties)
            return properties[args[2]][args[-1].split('=',1)[1]]
        env=b'V2_DATABASE_URL=postgresql+psycopg://v26_acceptance:fixture@127.0.0.1:55433/mikrotik_v26_acceptance\0V2_DEPLOYMENT_PROFILE=v26-isolated-acceptance\0'
        with patch.object(worker.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=env)) as process:
            self.assertEqual(worker.services(run),[('mikrotik-v26-api.service',True),('mikrotik-v26-web.service',False)])
            self.assertEqual(process.call_count,2)
        properties['mikrotik-v26-web.service']['User']='root'
        with patch.object(worker.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=env)),self.assertRaises(RuntimeError):
            worker.services(run)

    def test_static_cutover_is_not_applied_to_verified_vite_dev_webroot(self):
        code,report=self.simulate(vite=True)
        self.assertEqual(code,1)
        self.assertEqual(report['reason'],'VITE_DEV_CUTOVER_NOT_ENABLED')
        self.assertEqual(report['live_commit'],worker.BASELINE)
        self.assertEqual(report['migration'],'NOT_RUN')

    def test_office_preflight_has_no_build_credentials_or_live_apply(self):
        import sys
        from types import SimpleNamespace
        spec=importlib.util.spec_from_file_location('office_preflight',ROOT/'tools/deploy-v26-office.py')
        office=importlib.util.module_from_spec(spec);spec.loader.exec_module(office)
        def source(commit,path):
            return 'def preflight_main(): return 0\n' if path.endswith('deploy_v26_remote.py') else '# inert fixture'
        with patch.object(sys,'argv',['deploy-v26-office.py','--preflight-only']), \
             patch.object(office.subprocess,'check_output',return_value='a'*40), \
             patch.object(office,'source',side_effect=source),patch.object(office,'build_artifact') as build, \
             patch.object(office.getpass,'getpass') as password, \
             patch.object(office.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as command:
            self.assertEqual(office.main(),0)
        build.assert_not_called();password.assert_not_called()
        payload=command.call_args.kwargs['input']
        self.assertIn('raise SystemExit(preflight_main())',payload)
        self.assertNotIn('ADMIN =',payload)
        self.assertEqual(command.call_count,1)
