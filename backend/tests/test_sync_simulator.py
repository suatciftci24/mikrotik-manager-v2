"""Offline synthetic simulator tests. No existing demo store, DB, sockets or clients."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch,Mock
from fastapi import HTTPException
from pydantic import ValidationError
from app.simulation.engine import SCENARIOS,SimulatorEngine
from app.simulation.scenarios import operator,run
from app.simulation.report import create_report,read_report,write_report,Report
from app.integrations.contracts import Batch,Observation,SourceState,Backend
AT=datetime(2026,10,28,12,tzinfo=timezone.utc);RID=next(iter(SCENARIOS));SUB=RID+':subscriber:new'
def observation(kind='PPPOE',status='ACTIVE',revision=1,offset=0,**extra):return Observation(id=RID+':'+kind,router_id=RID,kind=kind,status=status,revision=revision,observed_at=AT+timedelta(seconds=offset),state=SourceState.AVAILABLE,**({'subject_id':SUB,'backend':'LOCAL','name':'Synthetic profile A'} if kind=='PPPOE' else {}),**extra)
def batch(cursor='one',sequence=1,records=None,**extra):return Batch(router_id=RID,cursor=cursor,sequence=sequence,records=tuple(records if records is not None else [observation()]),**extra)
class SimulatorTests(TestCase):
    def setUp(self):self.user=operator();self.engine=SimulatorEngine()
    def test_five_independent_scenarios_have_separate_accounts_cursors_faults_and_recovery(self):
        engine,user,at=run();rows=[engine.view(user,id,at) for id in SCENARIOS]
        self.assertEqual(len(rows),5);self.assertEqual(len({r['cursor'] for r in rows}),5);self.assertEqual(len({next(iter(r['subscribers'])) for r in rows}),5)
        self.assertEqual([r['error'] for r in rows],[None,'TIMEOUT',None,'ERROR','ERROR']);self.assertEqual(rows[2]['observations'][0]['router_id'],list(SCENARIOS)[2])
        self.assertTrue(all(not id.startswith('demo-sub-') for r in rows for id in r['subscribers']))
    def test_profile_disable_enable_expire_audit_and_closed_session_duration(self):
        engine,user,at=run();value=engine.view(user,RID,at)
        self.assertEqual([e['operation'] for e in value['audit'] if not e['operation'].startswith('SESSION_')],['CREATE','PROFILE_CHANGE','DISABLE','ENABLE','EXPIRE']);self.assertEqual(value['subscribers'][SUB]['status'],'EXPIRED')
        self.assertEqual(len(value['sessions']),2);self.assertEqual(next(iter(value['sessions'].values()))['duration_seconds'],20)
    def test_duplicate_batch_does_not_duplicate_subscriber_audit_or_session(self):
        rows=[observation(),observation('SESSION','ACTIVE',subject_id=SUB)];value=batch(records=rows)
        self.engine.ingest(self.user,RID,value,AT,None);before=self.engine.view(self.user,RID,AT)
        self.engine.ingest(self.user,RID,value,AT,None);after=self.engine.view(self.user,RID,AT)
        self.assertEqual(before['audit'],after['audit']);self.assertEqual(before['sessions'],after['sessions']);self.assertEqual(after['skipped'],2)
    def test_partial_failure_rolls_back_replica_audit_and_projection(self):
        self.engine.ingest(self.user,RID,batch(),AT,None);before=self.engine.view(self.user,RID,AT)
        with self.assertRaises(RuntimeError):self.engine.ingest(self.user,RID,batch('two',2,[observation(revision=2,offset=1)]),AT+timedelta(seconds=1),'one',fail_before_commit=True)
        self.assertEqual(self.engine.view(self.user,RID,AT),before)
    def test_bad_payload_cross_source_or_stale_cursor_cannot_mutate_last_good(self):
        self.engine.ingest(self.user,RID,batch(),AT,None);before=self.engine.view(self.user,RID,AT)
        for bad in [batch('two',2).model_copy(update={'source_id':'external'}),batch('two',2).model_copy(update={'router_id':'foreign'}),batch('delta',2,mode='DELTA',base_cursor='missing')]:
            with self.assertRaises((ValueError,HTTPException)):self.engine.ingest(self.user,RID,bad,AT,'one')
        self.assertEqual(self.engine.view(self.user,RID,AT),before)
    def test_old_sequence_and_timestamp_cannot_overwrite(self):
        self.engine.ingest(self.user,RID,batch(),AT,None)
        for bad in [batch('old',0),batch('late',2,[observation(revision=2,offset=-1)])]:
            with self.assertRaises(ValueError):self.engine.ingest(self.user,RID,bad,AT,'one')
    def test_backoff_and_timeout_preserve_last_good_and_other_routers(self):
        self.engine.ingest(self.user,RID,batch(),AT,None);self.engine.failure(self.user,RID,SourceState.TIMEOUT,AT,'one')
        with self.assertRaises(HTTPException):self.engine.ingest(self.user,RID,batch('two',2),AT,'one')
        self.engine.ingest(self.user,RID,batch('two',2),AT+timedelta(seconds=1),'one');self.assertIsNone(self.engine.view(self.user,RID,AT)['error'])
    def test_alarm_ack_does_not_resolve_and_repeated_down_does_not_duplicate(self):
        first=batch(records=[observation('WAN','DOWN')]);self.engine.ingest(self.user,RID,first,AT,None);self.engine.acknowledge(self.user,RID,'WAN')
        self.assertEqual(self.engine.view(self.user,RID,AT)['alarms']['WAN']['state'],'ACKNOWLEDGED')
        self.engine.ingest(self.user,RID,batch('down',2,[observation('WAN','DOWN',2,1)]),AT+timedelta(seconds=1),'one');self.assertEqual(len(self.engine.view(self.user,RID,AT)['alarms']),1)
        self.engine.ingest(self.user,RID,batch('up',3,[observation('WAN','UP',3,2)]),AT+timedelta(seconds=2),'down');self.assertEqual(self.engine.view(self.user,RID,AT)['alarms']['WAN']['state'],'RESOLVED')
    def test_unknown_or_stale_down_does_not_generate_alarm(self):
        for i,row in enumerate([observation('WAN','DOWN',offset=-86400),observation('WAN','UNKNOWN')]):
            engine=SimulatorEngine();engine.ingest(self.user,RID,batch(records=[row]),AT,None);self.assertEqual(engine.view(self.user,RID,AT)['alarms'],{})
    def test_unauthorized_owner_and_viewer_cannot_ingest(self):
        for user in [{**self.user,'permissions':{}},{**self.user,'role_code':'VIEWER'}]:
            with self.assertRaises(HTTPException):self.engine.ingest(user,RID,batch(),AT,None)
        self.engine.ingest(self.user,RID,batch(),AT,None)
        with self.assertRaises(HTTPException):self.engine.view({**self.user,'permissions':{}},RID,AT)
    def test_concurrent_cas_only_one_commit_and_one_audit(self):
        self.engine.ingest(self.user,RID,batch(),AT,None)
        def accept(id):
            try:self.engine.ingest(self.user,RID,batch(id,2,[observation(revision=2)]),AT,'one');return 200
            except HTTPException as e:return e.status_code
        with ThreadPoolExecutor(2) as pool:self.assertEqual(sorted(pool.map(accept,['two-a','two-b'])),[200,409])
        self.assertEqual(len(self.engine.view(self.user,RID,AT)['audit']),2)
    def test_report_is_strict_and_contains_no_credentials_or_external_endpoints(self):
        report=create_report();value=report.model_dump_json();self.assertNotIn('secretref:',value);self.assertNotIn('password',value);self.assertNotIn('://',value)
        with self.assertRaises(ValidationError):Report.model_validate({**report.model_dump(),'token':'secret'})
    def test_disabled_by_default_read_does_not_run_simulator_and_filters_totals(self):
        with TemporaryDirectory() as temp,patch('app.simulation.report.DIRECTORY',Path(temp)),patch('app.simulation.scenarios.run') as runner:
            result=read_report(self.user);self.assertFalse(result['enabled']);self.assertEqual(result['status'],'DISABLED');runner.assert_not_called()
        report=create_report()
        with TemporaryDirectory() as temp,patch('app.simulation.report.DIRECTORY',Path(temp)):
            write_report(report);limited={**self.user,'permissions':{SCENARIOS[RID]:{'can_view':True,'can_view_reports':True}}};result=read_report(limited,page_size=1)
            self.assertEqual(result['total'],sum(v==SCENARIOS[RID] for v in SCENARIOS.values()));self.assertEqual(len(result['items']),1);self.assertTrue(all(r['owner_router_id']==SCENARIOS[RID] for r in result['items']))
    def test_publication_failure_and_rerun_preserve_old_report_and_archives(self):
        with TemporaryDirectory() as temp,patch('app.simulation.report.DIRECTORY',Path(temp)):
            first=create_report();write_report(first);old=Path(temp,'latest.json').read_bytes()
            with patch('app.simulation.report.os.replace',side_effect=OSError('synthetic')):
                with self.assertRaises(OSError):write_report(create_report())
            self.assertEqual(Path(temp,'latest.json').read_bytes(),old);second=create_report();write_report(second);self.assertNotEqual(first.run_id,second.run_id);self.assertTrue(Path(temp,str(first.run_id)+'.json').exists())
    def test_corrupt_or_symlinked_artifact_fails_closed_without_secret_echo(self):
        with TemporaryDirectory() as temp,patch('app.simulation.report.DIRECTORY',Path(temp)):
            Path(temp,'latest.json').write_text('{"password":"secretref:v2/private/key"}')
            result=read_report(self.user);self.assertEqual(result['status'],'UNKNOWN');self.assertNotIn('private',str(result))
            Path(temp,'latest.json').unlink();Path(temp,'latest.json').symlink_to('/tmp/nonexistent-v2')
            self.assertEqual(read_report(self.user)['status'],'UNKNOWN')
    def test_http_surface_is_admin_get_only(self):
        from app.api.v1.system import router
        from app.core.security import current_admin
        route=next(r for r in router.routes if r.path=='/system/simulator');self.assertEqual(route.methods,{'GET'});self.assertIn(current_admin,[d.call for d in route.dependant.dependencies])

    def test_foreign_subject_namespace_or_changed_authority_is_rejected(self):
        self.engine.ingest(self.user,RID,batch(),AT,None)
        first=observation(revision=2).model_copy(update={'subject_id':'demo-sub-existing'})
        second=observation(revision=2).model_copy(update={'backend':Backend.RADIUS})
        for row in [first,second]:
            with self.assertRaises(ValueError):self.engine.ingest(self.user,RID,batch('two',2,[row]),AT,'one')
        self.assertEqual(len(self.engine.view(self.user,RID,AT)['audit']),1)
    def test_explicit_command_without_run_flag_never_executes(self):
        from app.sync_simulator import main
        with patch('app.sync_simulator.create_report') as create,redirect_stdout(StringIO()):
            self.assertEqual(main([]),0);create.assert_not_called()
    def test_retry_backoff_is_deterministic_and_capped(self):
        delays=[]
        for _ in range(8):
            self.engine.failure(self.user,RID,SourceState.TIMEOUT,AT,None)
            delays.append((self.engine.view(self.user,RID,AT)['retry_at']-AT).total_seconds())
        self.assertEqual(delays,[1,2,4,8,16,32,60,60])

    def test_future_or_missing_operation_timestamp_never_creates_account(self):
        for row in [observation(offset=1),observation().model_copy(update={'observed_at':None})]:
            with self.assertRaises(ValueError):self.engine.ingest(self.user,RID,batch(records=[row]),AT,None)
        self.assertEqual(self.engine.view(self.user,RID,AT)['subscribers'],{})
