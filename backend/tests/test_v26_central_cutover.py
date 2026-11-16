"""New cutover transaction tests. All processes, services and database calls are synthetic."""
import base64
import io
import json
from pathlib import Path
import shutil
import tempfile
from contextlib import ExitStack,redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.tests import test_v26_central_development as fixtures
ROOT=fixtures.ROOT


class CentralCutover(unittest.TestCase):
    def simulate(self,client_failure=False,proof_failure=False,unsafe=False,residue=False,residue_drift=False):
        remote=fixtures.CentralDevelopment().remote()
        with tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
            app=Path(temp)/'app';(app/'.venv').mkdir(parents=True)
            state=app/'.local';state.mkdir(mode=0o700)
            root=state/'central';root.mkdir(mode=0o700)
            dev=root/'dev-venv';dev.mkdir()
            (root/'dev-environment.json').write_text('{}')
            live={'head':remote.BASELINE,'database':'d'*64,'running':True}
            events=[];units=[('v26-api.service',True),('v26-web.service',False)]
            identity=dict(instance='12345678-1234-1234-1234-123456789abc',database='d'*64,checkout=str(app),origin=remote.ORIGIN)
            (root/'identity.json').write_text(json.dumps(identity))
            def git(*args):
                events.append(('git',args[0]))
                if args[0]=='rev-parse':return live['head']
                if args[0]=='status':return ''
                if args[0]=='switch' and '--detach' in args:live['head']=args[-1]
                if args[0]=='merge':live['head']=remote.TARGET
                return ''
            def run(args,*,stage,**kw):
                events.append(('run',stage))
                if stage=='CENTRAL_DEV_PREFIX':return str(dev)
                if stage=='CENTRAL_V26_STOP':live['running']=False
                if stage in ('CENTRAL_V26_START','CENTRAL_ROLLBACK_START'):live['running']=True
                if stage=='CENTRAL_ROLLBACK_DROPIN_READ':return Path(args[-1]).read_text()
                return ''
            def command(args,**kw):
                if 'pg_dump' in str(args):
                    events.append(('backup',live['running']))
                    kw['stdout'].write(b'synthetic dump')
                if args[:3]==['sudo','-n','test']:return SimpleNamespace(returncode=0 if residue else 1)
                if '-m' in args and 'unittest' in args:
                    events.append(('target_tests',live['running']))
                    self.assertNotEqual(kw['cwd'],str(app))
                return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
            def extract(data,path,kind):
                if kind=='source':(path/'backend/app').mkdir(parents=True)
                else:(path/'dist').mkdir()
            def proof_main():
                events.append(('proof',live['running']))
                attempt=Path(remote.CURRENT_ATTEMPT)
                print(json.dumps(dict(status='BLOCKED' if proof_failure else 'PASS',migration_runs=2,
                                      backup_sha256=remote.digest_file(attempt/'database.dump'))))
                return 1 if proof_failure else 0
            def snapshot(query,*,stage):
                events.append(('snapshot',stage,live['running']))
                return {'users':{'hash':'preserved'}}
            def preserved(a,b):self.assertEqual(a,b)
            def install(unit,path):
                events.append(('install',unit))
                shutil.copyfile(path,root/(unit+'.dropin'))
            def accept(profile,ready):
                events.append(('client',live['running']))
                self.assertFalse((root/'current.json').exists())
                # setup.lock remains held across the acknowledgement.
                import fcntl
                with (root/'setup.lock').open('a') as contender:
                    with self.assertRaises(BlockingIOError):fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)
                if unsafe:live['database']='wrong'
                if client_failure:raise RuntimeError('CLIENT_ACCEPTANCE_FAILED')
            props=dict(Type='simple',KillMode='control-group',ExecStartPre='',ExecStartPost='',ExecStop='',ExecStopPost='')
            stack.enter_context(patch.multiple(remote,create=True,APP=str(app),APP_PATH=app,ROOT=root,
                SOURCE_B64=base64.b64encode(b'source').decode(),DIST_B64=base64.b64encode(b'dist').decode(),
                DIST_SHA=remote.hashlib.sha256(b'dist').hexdigest()))
            for name,value in [('git',git),('run',run),('extract',extract),('verify_source',lambda *a:None),
                ('db_identity',lambda:live['database']),('unit_properties',lambda unit:props),
                ('dropin_path',lambda unit:root/(unit+'.dropin')),('install_dropin',install),
                ('public_accept',lambda profile:{'build_id':'b'*64}),('warm_api',lambda:None),
                ('installed_units',lambda profile:units),('load',lambda *a,**kw:{'main':proof_main})]:
                stack.enter_context(patch.object(remote,name,side_effect=value))
            if residue:
                def verify_residue(units,head):
                    events.append(('residue_check',live['running']))
                    if residue_drift and events.count(('residue_check',True))>1:
                        raise RuntimeError('UNOWNED_CENTRAL_DROPIN_EXISTS')
                    return {unit:b'' for unit,_ in units}
                stack.enter_context(patch.object(remote,'verified_initial_dropins',side_effect=verify_residue))
            def captured_tests(argv,cwd,env,evidence,target):
                result=command(argv,cwd=cwd,env=env)
                return dict(status='TESTS_PASS' if result.returncode==0 else 'BLOCKED')
            stack.enter_context(patch.dict(remote.D,{'test_evidence':captured_tests}))
            stack.enter_context(patch.object(remote.subprocess,'run',side_effect=command))
            stack.enter_context(patch.dict(remote.W,{'nginx_routes':lambda text:{}}))
            stack.enter_context(patch.dict(remote.L,{'stash_pin':lambda run:('pinned','oid'),'services':lambda run:units,
                                                   'ready':lambda opener:None,'admin_check':lambda opener:None}))
            stack.enter_context(patch.dict(remote.H,{'snapshot':snapshot,'assert_preserved':preserved}))
            failure=None
            try:remote.setup(client_accept=accept)
            except RuntimeError as error:failure=str(error)
            attempt=Path(remote.CURRENT_ATTEMPT)
            rollback=json.loads((attempt/'rollback.json').read_text()) if (attempt/'rollback.json').exists() else None
            return dict(events=events,failure=failure,rollback=rollback,pointer=(root/'current.json').exists(),
                        live=dict(live),baseline=remote.BASELINE)

    def test_online_preparation_precedes_stop_and_ack_precedes_commit(self):
        result=self.simulate()
        self.assertIsNone(result['failure']);self.assertTrue(result['pointer'])
        events=result['events'];stop=events.index(('run','CENTRAL_V26_STOP'))
        for event in [('backup',True),('proof',True),('target_tests',True)]:self.assertLess(events.index(event),stop)
        self.assertIn(('snapshot','CENTRAL_DATA_BEFORE',False),events)
        self.assertIn(('client',True),events)

    def test_isolated_failure_never_stops_or_changes_live_checkout(self):
        result=self.simulate(proof_failure=True)
        self.assertEqual(result['failure'],'CENTRAL_FRESH_RESTORE_MIGRATION_ACCEPTANCE_FAILED')
        self.assertFalse(result['pointer']);self.assertEqual(result['live']['head'],result['baseline'])
        self.assertEqual(result['rollback']['status'],'NOT_REQUIRED')
        self.assertNotIn(('run','CENTRAL_V26_STOP'),result['events'])
        self.assertFalse(any(event[0]=='install' for event in result['events']))

    def test_office_rejection_restores_baseline_without_database_restore(self):
        result=self.simulate(client_failure=True)
        self.assertEqual(result['failure'],'CLIENT_ACCEPTANCE_FAILED')
        self.assertFalse(result['pointer']);self.assertEqual(result['live']['head'],result['baseline'])
        self.assertTrue(result['live']['running'])
        self.assertEqual(result['rollback']['status'],'BASELINE_VERIFIED')
        self.assertFalse(result['rollback']['db_restore_performed'])
        self.assertIn(('snapshot','CENTRAL_ROLLBACK_DATA',True),result['events'])

    def test_unsafe_rollback_never_claims_verification_or_restores_database(self):
        result=self.simulate(client_failure=True,unsafe=True)
        self.assertEqual(result['failure'],'CENTRAL_ROLLBACK_UNSAFE_BINDING')
        self.assertIsNone(result['rollback']);self.assertFalse(result['pointer'])
        self.assertNotIn(('run','CENTRAL_ROLLBACK_STOP'),result['events'])

    def test_ack_rejection_disconnect_timeout_and_wrong_version_fail_closed(self):
        remote=fixtures.CentralDevelopment().remote()
        profile=dict(origin=remote.ORIGIN,instance='i',commit='a'*40,database='d'*64)
        good={**profile,'release':profile['commit'],'location':'office','machine':'a'*64,
              'view_hash':'b'*64,'build_id':'c'*64,'captured_at':remote.time.time()}
        good.pop('commit')
        for line,expected in [('', 'CLIENT_ACCEPTANCE_DISCONNECTED'),('{"event":"CLIENT_REJECTED"}\n','CLIENT_ACCEPTANCE_FAILED'),
                              (json.dumps({**good,'release':'f'*40}),'CLIENT_BINDING_REJECTED')]:
            with self.subTest(reason=expected),patch.object(remote.sys,'stdin',io.StringIO(line)),redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError,expected):remote.client_acceptance(profile,{'build_id':'c'*64})
        def timed_read():raise RuntimeError('CLIENT_ACCEPTANCE_TIMEOUT')
        with patch.object(remote.sys,'stdin',SimpleNamespace(readline=timed_read)),redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'CLIENT_ACCEPTANCE_TIMEOUT'):remote.client_acceptance(profile,{'build_id':'c'*64})

    def test_valid_receipt_is_required_and_deadline_interrupts_partial_input(self):
        remote=fixtures.CentralDevelopment().remote()
        profile=dict(origin=remote.ORIGIN,instance='i',commit='a'*40,database='d'*64)
        receipt=dict(origin=remote.ORIGIN,instance='i',release='a'*40,database='d'*64,
                     location='office',machine='a'*64,view_hash='b'*64,build_id='c'*64,captured_at=remote.time.time())
        with patch.object(remote.sys,'stdin',io.StringIO(json.dumps(receipt))),redirect_stdout(io.StringIO()):
            self.assertEqual(remote.client_acceptance(profile,{'build_id':'c'*64}),receipt)
        previous=remote.signal.getsignal(remote.signal.SIGALRM)
        def partial_input():remote.signal.getsignal(remote.signal.SIGALRM)(None,None)
        with patch.object(remote.sys,'stdin',SimpleNamespace(readline=partial_input)),redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'CLIENT_ACCEPTANCE_TIMEOUT'):remote.client_acceptance(profile,{'build_id':'c'*64})
        self.assertEqual(remote.signal.getsignal(remote.signal.SIGALRM),previous)

    def test_office_sends_abort_and_waits_for_remote_rollback_result(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('office_cutover',ROOT/'tools/central-v26-office.py')
        office=importlib.util.module_from_spec(spec);spec.loader.exec_module(office)
        class Sink(io.BytesIO):
            def close(self):pass
        remote_report=dict(status='BLOCKED',reason='CLIENT_ACCEPTANCE_FAILED',
                           rollback=dict(status='BASELINE_VERIFIED',db_restore_performed=False))
        channel=SimpleNamespace(stdin=Sink(),stdout=io.BytesIO((json.dumps(dict(event='CENTRAL_READY',profile={},ready={}))+'\n'+
                                json.dumps(remote_report)+'\n').encode()),poll=lambda:0,wait=lambda *a,**kw:0)
        output=io.StringIO()
        with patch.object(office.sys,'argv',['central-v26-office.py','--verify-location','office']), \
             patch.object(office,'git',side_effect=lambda *args:'' if args[0]=='status' else 'a'*40), \
             patch.object(office,'source',return_value=''),patch('builtins.input',return_value='fixture'), \
             patch.object(office.getpass,'getpass',return_value='not-a-real-secret'), \
             patch.object(office.subprocess,'Popen',return_value=channel), \
             patch.object(office,'observe',side_effect=RuntimeError('BINDING_REJECTED')),redirect_stdout(output):
            self.assertEqual(office.main(),1)
        self.assertTrue(channel.stdin.getvalue().endswith(b'{"event": "CLIENT_REJECTED"}\n'))
        self.assertEqual(json.loads(output.getvalue()),remote_report)
        self.assertNotIn('not-a-real-secret',output.getvalue())

    def test_missing_office_acceptor_is_rejected_before_any_command(self):
        remote=fixtures.CentralDevelopment().remote()
        with patch.object(remote,'git') as git,patch.object(remote,'run') as command:
            with self.assertRaisesRegex(RuntimeError,'CLIENT_ACCEPTANCE_REQUIRED'):remote.setup(client_accept=None)
        git.assert_not_called();command.assert_not_called()

    def test_evidenced_empty_residue_is_rechecked_before_switch_and_preserved_on_rollback(self):
        result=self.simulate(residue=True,client_failure=True)
        self.assertEqual(result['events'].count(('residue_check',True)),2)
        self.assertEqual(result['failure'],'CLIENT_ACCEPTANCE_FAILED')
        self.assertEqual(result['rollback']['status'],'BASELINE_VERIFIED')
        self.assertFalse(result['pointer'])

    def test_residue_drift_during_online_preparation_blocks_before_stop(self):
        result=self.simulate(residue=True,residue_drift=True)
        self.assertEqual(result['failure'],'UNOWNED_CENTRAL_DROPIN_EXISTS')
        self.assertNotIn(('run','CENTRAL_V26_STOP'),result['events'])
        self.assertFalse(result['pointer'])
