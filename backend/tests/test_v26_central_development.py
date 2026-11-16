"""Pure central-development gates. No real DB, SSH, services or credentials."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('central_policy',ROOT/'tools/v26_central_policy.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)


class CentralDevelopment(unittest.TestCase):
    def profile(self):
        return dict(instance='12345678-1234-1234-1234-123456789abc',database='d'*64,commit='a'*40)

    def receipt(self,location,machine):
        return dict(origin=policy.ORIGIN,instance=self.profile()['instance'],release='a'*40,database='d'*64,
                    location=location,machine=machine*64,view_hash='e'*64,build_id='b'*64,captured_at=1000)

    def test_office_alone_or_same_machine_cannot_be_pass(self):
        office=self.receipt('office','1')
        self.assertIsNotNone(policy.complete_receipts([office],self.profile(),1001))
        home=self.receipt('home','1')
        self.assertEqual(policy.complete_receipts([office,home],self.profile(),1001),'INDEPENDENT_MACHINES_REQUIRED')

    def test_independent_current_same_origin_release_and_data_are_required(self):
        rows=[self.receipt('office','1'),self.receipt('home','2')]
        self.assertIsNone(policy.complete_receipts(rows,self.profile(),1001))
        for field,value in [('release','f'*40),('database','f'*64),('origin','https://other.example'),
                            ('view_hash','f'*64),('build_id','f'*64),('captured_at',0),('captured_at','secret')]:
            changed=[dict(row) for row in rows];changed[1][field]=value
            with self.subTest(field=field):self.assertIsNotNone(policy.complete_receipts(changed,self.profile(),1001))

    def test_db_identity_pins_cluster_database_and_port_without_password(self):
        value=dict(database=policy.DB,port='55433',data_directory='/var/lib/postgresql/16/v26',system_identifier='123',oid='456')
        self.assertEqual(len(policy.database_fingerprint(value)),64)
        for field,item in [('database','v1'),('port','5432'),('data_directory','/var/lib/postgresql/16/main')]:
            with self.subTest(field=field),self.assertRaises(RuntimeError):policy.database_fingerprint({**value,field:item})

    def test_static_config_has_one_existing_port_and_no_dev_or_db_upstream(self):
        text=policy.static_config(policy.APP+'/.local/central/releases/'+'a'*40+'/dist',
                                  policy.APP+'/.local/central/attempt-fixture/static',self.profile())
        self.assertEqual(text.count('listen '),1)
        self.assertIn('listen 127.0.0.1:15173;',text)
        self.assertNotIn('proxy_pass',text)
        self.assertNotIn('18996',text)
        self.assertIn('location /@vite { return 404; }',text)
        self.assertIn('location /src/ { return 404; }',text)
        for path in ['/srv/v1/dist',policy.APP+'/.local/central/bad;return 200']:
            with self.assertRaises(RuntimeError):policy.static_config(path,policy.APP+'/.local/central/runtime',self.profile())

    def test_test_runner_clears_panel_db_secrets_and_optins(self):
        spec=importlib.util.spec_from_file_location('central_test_runner',ROOT/'tools/central-v26-tests.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        from types import SimpleNamespace
        with patch.object(runner.Path,'cwd',return_value=runner.APP), \
             patch.object(runner.Path,'resolve',return_value=runner.APP),patch.object(runner.Path,'is_file',return_value=True), \
             patch.object(runner.sys,'argv',['runner','backend.tests.test_v26_central_development']), \
             patch.dict(runner.os.environ,{'V2_DATABASE_URL':'private panel URL','PGPASSWORD':'secret','V2_RUN_POSTGRES_TESTS':'1'}), \
             patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(runner.main(),0)
        env=run.call_args.kwargs['env']
        self.assertNotIn('PGPASSWORD',env)
        self.assertNotIn('V2_RUN_POSTGRES_TESTS',env)
        self.assertIn(':1/isolated_only',env['V2_DATABASE_URL'])
        self.assertNotIn('private panel URL',json.dumps(env))

    def test_immutable_release_reuses_only_canonical_existing_mutable_state(self):
        import tempfile
        from app.core import central_paths
        with patch.dict(central_paths.os.environ,{},clear=True):
            self.assertEqual(central_paths.state_root('/fixture/old/.local'),Path('/fixture/old/.local'))
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)/'state';base.mkdir(mode=0o700)
            env=dict(V2_CENTRAL_STATE_ROOT=str(base),V2_DEPLOYMENT_PROFILE='v26-isolated-acceptance')
            with patch.object(central_paths,'CENTRAL_ROOT',base),patch.dict(central_paths.os.environ,env,clear=True):
                self.assertEqual(central_paths.state_root('/different/release/.local'),base)
                with patch.dict(central_paths.os.environ,{'V2_DEPLOYMENT_PROFILE':'local-demo'}),self.assertRaises(RuntimeError):
                    central_paths.state_root('/fixture')
                alias=Path(temp)/'alias';alias.symlink_to(base,target_is_directory=True)
                with patch.dict(central_paths.os.environ,{'V2_CENTRAL_STATE_ROOT':str(alias)}),self.assertRaises(RuntimeError):
                    central_paths.state_root('/fixture')
                base.chmod(0o777)
                with self.assertRaises(RuntimeError):central_paths.state_root('/fixture')

    def remote(self):
        spec=importlib.util.spec_from_file_location('central_remote_fixture',ROOT/'tools/v26_central_remote.py')
        module=importlib.util.module_from_spec(spec)
        module.POLICY=(ROOT/'tools/v26_central_policy.py').read_text()
        module.HELPER='def run(*a, **kw): raise RuntimeError("UNEXPECTED_COMMAND")\n'
        module.LEGACY=(ROOT/'tools/deploy_v26_remote.py').read_text()
        module.WEBROOT=(ROOT/'tools/v26_webroot_preflight.py').read_text()
        module.DIAGNOSTICS=(ROOT/'tools/v26_acceptance_diagnostics.py').read_text()
        module.CANDIDATE_PROBE=(ROOT/'tools/v26_candidate_probe.py').read_text()
        module.ADMIN={};module.TARGET='a'*40;module.ACTION='apply';module.MIGRATION_SQL='fixture'
        spec.loader.exec_module(module)
        return module

    def test_same_commit_setup_is_idempotent_without_restart_backup_or_checkout(self):
        import tempfile,hashlib
        from unittest.mock import Mock
        remote=self.remote()
        with tempfile.TemporaryDirectory() as temp:
            app=Path(temp)/'app';(app/'.venv').mkdir(parents=True)
            base=app/'.local/central';base.mkdir(parents=True,mode=0o700)
            config=base/'nginx.conf';config.write_text('fixture only')
            identity=dict(instance=self.profile()['instance'],database='d'*64,checkout=str(app),origin=policy.ORIGIN)
            (base/'identity.json').write_text(json.dumps(identity))
            profile={**identity,'commit':'a'*40,'web_argv':['nginx','-c',str(config)],
                     'static_config_sha256':hashlib.sha256(config.read_bytes()).hexdigest()}
            pointer=base/'current.json';pointer.write_text(json.dumps(profile));before=pointer.read_bytes()
            calls=[]
            def git(*args):
                calls.append(args)
                if args[0]=='status':return ''
                if args[0]=='rev-parse':return 'a'*40
                if args==('branch','--show-current'):return 'main-guncel'
                raise AssertionError('Unexpected Git mutation '+str(args))
            with patch.multiple(remote,APP=str(app),APP_PATH=app,ROOT=base), \
                 patch.object(remote,'git',side_effect=git),patch.object(remote,'db_identity',return_value='d'*64), \
                 patch.object(remote,'installed_units',return_value=[]),patch.object(remote,'public_accept',return_value={'build_id':'b'*64}), \
                 patch.object(remote,'run',return_value='config'), \
                 patch.dict(remote.L,{'stash_pin':lambda run:('unchanged','oid')}), \
                 patch.dict(remote.W,{'nginx_routes':lambda text:{}}), \
                 patch.object(remote.subprocess,'run') as command,patch.object(remote.shutil,'copytree') as copy:
                result,_=remote.setup()
            self.assertEqual(result,profile);self.assertEqual(pointer.read_bytes(),before)
            command.assert_not_called();copy.assert_not_called()
            self.assertTrue(all(args[0] in ('status','rev-parse','branch') for args in calls))

    def test_git_source_archive_extracts_to_new_release_only(self):
        import subprocess,tempfile,io,tarfile
        remote=self.remote()
        archive=subprocess.check_output(['git','archive','HEAD','backend/app','migrations'],cwd=ROOT)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);remote.extract(archive,root,'source')
            self.assertTrue((root/'backend/app/main.py').is_file())
            self.assertTrue((root/'migrations/versions/011_package_catalog.sql').is_file())
            with patch.object(remote,'git',side_effect=lambda *args:subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()):
                commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
                remote.verify_source(root,commit)
                main=root/'backend/app/main.py';main.write_bytes(main.read_bytes()+b'\n# changed fixture\n')
                with self.assertRaisesRegex(RuntimeError,'CENTRAL_SOURCE_BLOB_CHANGED'):remote.verify_source(root,commit)
            malicious=io.BytesIO()
            with tarfile.open(fileobj=malicious,mode='w') as tar:
                info=tarfile.TarInfo('backend/app/../../private');info.size=1;tar.addfile(info,io.BytesIO(b'x'))
            with self.assertRaises(RuntimeError):remote.extract(malicious.getvalue(),root,'source')

    def test_source_inventory_validates_derived_bytecode_without_ignoring_extras(self):
        import subprocess,tempfile,py_compile
        remote=self.remote()
        archive=subprocess.check_output(['git','archive','HEAD','backend/app','migrations'],cwd=ROOT)
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        with tempfile.TemporaryDirectory() as temp,patch.object(remote,'git',side_effect=lambda *args:
                subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()):
            root=Path(temp);remote.extract(archive,root,'source')
            clean=remote.verify_source(root,commit)
            source=root/'backend/app/__init__.py'
            # A real compiler-generated file is absent from Git's source manifest.
            cache=Path(py_compile.compile(str(source),doraise=True))
            self.assertNotIn(str(cache.relative_to(root)),subprocess.check_output(
                ['git','ls-tree','-r','--name-only',commit,'backend/app','migrations'],cwd=ROOT,text=True).splitlines())
            checked=remote.verify_source(root,commit)
            self.assertEqual(checked['actual_files'],clean['actual_files']+1)
            self.assertEqual(checked['verified_cache_files'],1)
            for mode in (py_compile.PycInvalidationMode.CHECKED_HASH,py_compile.PycInvalidationMode.UNCHECKED_HASH):
                py_compile.compile(str(source),doraise=True,invalidation_mode=mode)
                self.assertEqual(remote.verify_source(root,commit)['verified_cache_files'],1)
            py_compile.compile(str(source),dfile='/different/source.py',doraise=True)
            with self.assertRaisesRegex(RuntimeError,'CENTRAL_SOURCE_EXTRA_FILE_REJECTED'):remote.verify_source(root,commit)
            py_compile.compile(str(source),doraise=True)
            original=cache.read_bytes()
            for raw in (original+b'extra',b'bad magic'+original[9:],original[:16]+b'untrusted executable payload'):
                with self.subTest(kind=raw[:4]):
                    cache.write_bytes(raw)
                    with self.assertRaisesRegex(RuntimeError,'CENTRAL_SOURCE_EXTRA_FILE_REJECTED') as caught:
                        remote.verify_source(root,commit)
                    self.assertEqual(caught.exception.details['unexpected_files'],1)
                    self.assertNotIn('untrusted',json.dumps(caught.exception.details))
            cache.write_bytes(original)
            for name in ('unexpected.py','unexpected.txt','__pycache__/orphan.cpython-311.pyc'):
                extra=root/'backend/app'/name;extra.write_bytes(b'private-token')
                with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'CENTRAL_SOURCE_EXTRA_FILE_REJECTED'):
                    remote.verify_source(root,commit)
                extra.unlink()
            cache.unlink();cache.symlink_to(source)
            with self.assertRaisesRegex(RuntimeError,'CENTRAL_SOURCE_SYMLINK_REJECTED'):remote.verify_source(root,commit)

    def test_installed_api_cannot_point_at_mutable_checkout(self):
        remote=self.remote();profile=self.profile()
        profile.update(origin=policy.ORIGIN,checkout=policy.APP,release=str(remote.ROOT/'releases'/profile['commit']),
                       units=[['v26-api.service',True],['v26-web.service',False]],
                       api_argv=[str(remote.APP_PATH/'.venv/bin/python'),'-m','uvicorn','app.main:app'],
                       web_argv=['/usr/sbin/nginx','-c',str(remote.ROOT/'attempt-x/config'),'-p',str(remote.ROOT/'attempt-x/runtime')])
        with patch.object(remote,'db_identity',return_value=profile['database']),self.assertRaisesRegex(RuntimeError,'CENTRAL_EXEC_BINDING_REJECTED'):
            remote.installed_units(profile)
