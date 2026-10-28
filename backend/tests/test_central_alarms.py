from copy import deepcopy
from datetime import datetime, timezone
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4
import json
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from app.services.alarms import combine, identity, project_alarms
from app.adapters import alarm_actions as storage
from app.api.v1 import alarms as routes
from app.core.security import current_alarm_mutator, current_demo_user
from app.services.demo_subscriptions import DemoChangeError, DemoStorageUnavailable
from app.services.demo_data import ROUTERS
from app.services.demo_examples import demo_examples

AT=datetime(2026,10,28,12,tzinfo=timezone.utc)
def record(occurrence='demo-source-1',state='OPEN',first='2026-10-28T09:00:00Z',last='2026-10-28T10:00:00Z'):
    return dict(router_id=ROUTERS[0]['id'],kind='WAN_DOWN',severity='P2',occurrence_id=occurrence,source_state=state,first_seen=first,last_seen=last,title='Demo WAN',evidence='Synthetic',source='router-events',source_id=occurrence)

class AlarmProjectionTests(TestCase):
    def test_duplicate_source_is_one_alarm_and_polling_does_not_increase_count(self):
        row=record();results=combine([row,row],[],'demo-user')
        self.assertEqual(len(results),1);self.assertEqual(results[0]['repeat_count'],1)
        self.assertEqual(results,combine([row],[],'demo-user'))

    def test_same_problem_merges_episodes_without_carrying_old_ack_forward(self):
        old=record('old',first='2026-10-28T11:00:00+03:00',last='2026-10-28T11:00:00+03:00')
        new=record('new',last='2026-10-28T10:00:00Z')
        ack=dict(id='a',alarm_id=identity(old['router_id'],'WAN_DOWN'),occurrence_id='old',action='ACK',actor_id='demo-user')
        result=combine([old,new],[ack],'demo-user')[0]
        self.assertEqual(result['first_seen'],old['first_seen']);self.assertEqual(result['repeat_count'],2)
        self.assertEqual(result['state'],'OPEN');self.assertIsNone(result['acknowledgement'])

    def test_ack_and_notification_read_never_resolve_or_share_user_read_state(self):
        row=record();aid=identity(row['router_id'],row['kind'])
        actions=[dict(id='a',alarm_id=aid,occurrence_id=row['occurrence_id'],action='ACK',actor_id='demo-user'),dict(id='r',alarm_id=aid,occurrence_id=row['occurrence_id'],action='READ',actor_id='demo-other')]
        result=combine([row],actions,'demo-user')[0]
        self.assertEqual(result['state'],'ACKNOWLEDGED');self.assertFalse(result['notification_read'])
        for state in ('RECOVERING','RESOLVED'):
            self.assertEqual(combine([{**row,'source_state':state}],actions,'demo-user')[0]['state'],state)

    def test_actual_seed_source_is_readonly_and_expiry_does_not_invent_times(self):
        items=[row['item'] for row in demo_examples(AT)]
        expired={**items[0],'id':'demo-sub-expiry-fixture','demo_report':None,'expires_on':'2026-10-27'}
        before=deepcopy(items+[expired]);alarms,coverage=project_alarms(items+[expired],ROUTERS,[],'demo-user',AT)
        self.assertEqual(items+[expired],before)
        self.assertTrue(coverage['connection_available']);self.assertFalse(coverage['ipsec_available'])
        target=next(row for row in alarms if row['kind']=='PPPOE_EXPIRE')
        self.assertIsNone(target['first_seen']);self.assertIsNone(target['last_seen'])
        self.assertFalse(any(row['kind']=='IPSEC_DOWN' for row in alarms))

    def test_source_disappearance_keeps_ack_evidence_without_claiming_resolution(self):
        row=record();aid=identity(row['router_id'],row['kind'])
        action=dict(id='old-ack',alarm_id=aid,occurrence_id=row['occurrence_id'],action='ACK',actor_id='demo-user',source_snapshot=row)
        archived=combine([],[action],'demo-user')[0]
        self.assertFalse(archived['source_available']);self.assertEqual(archived['state'],'ACKNOWLEDGED')
        self.assertEqual(archived['source_state'],'OPEN')

    def test_expiry_does_not_assume_untyped_or_future_accounts_are_expired(self):
        items=[row['item'] for row in demo_examples(AT)]
        for item in items:item['access_type']=None;item['expires_on']='2026-10-27'
        result,_=project_alarms(items,ROUTERS,[],'demo-user',AT)
        self.assertFalse(any(row['kind']=='PPPOE_EXPIRE' for row in result))

    def test_new_source_episode_keeps_prior_ack_memory_without_reusing_ack(self):
        old=record('old');new=record('new')
        aid=identity(old['router_id'],old['kind'])
        action=dict(id='old-ack',alarm_id=aid,occurrence_id='old',action='ACK',actor_id='demo-user',source_snapshot=old)
        result=combine([new],[action],'demo-user')[0]
        self.assertEqual(result['repeat_count'],2);self.assertTrue(result['source_available'])
        self.assertEqual(result['state'],'OPEN');self.assertIsNone(result['acknowledgement'])

    def test_permission_confirmation_and_openapi_contracts(self):
        admin=dict(id='demo-user',role='Sistem Yöneticisi',is_demo=True)
        self.assertEqual(current_alarm_mutator(admin,'alarm-ack'),admin)
        for user,header in [({**admin,'role':'Gözlemci'},'alarm-ack'),(admin,None),({**admin,'is_demo':False},'alarm-ack')]:
            with self.assertRaises(HTTPException):current_alarm_mutator(user,header)
        with self.assertRaises(ValidationError):routes.AlarmAction(request_id=uuid4(),occurrence_id='x',confirmed=False)
        ack=next(r for r in routes.router.routes if r.path=='/alarms/{alarm_id}/ack')
        self.assertIn(current_alarm_mutator,[d.call for d in ack.dependant.dependencies])
        read=next(r for r in routes.router.routes if r.path=='/alarms/{alarm_id}/read')
        self.assertIn(current_demo_user,[d.call for d in read.dependant.dependencies])

    def test_list_payload_does_not_ship_audit_snapshots_or_full_evidence_histories(self):
        alarm=combine([record()],[],'demo-user')[0]
        alarm['mika']={'history':['large-source-history']}
        alarm['action_history']=[{'id':'a','source_snapshot':{'private':'internal source copy'},'action':'ACK'}]
        self.assertNotIn('action_history',routes.public_alarm(alarm))
        self.assertNotIn('mika',routes.public_alarm(alarm))
        detail=routes.public_alarm(alarm,detail=True)
        self.assertNotIn('source_snapshot',detail['action_history'][0])
        self.assertIn('mika',detail)

    def test_date_filter_excludes_unknown_time_and_critical_count_includes_ack(self):
        rows=combine([record(),{**record('sub'),'kind':'PPPOE_EXPIRE','first_seen':None,'last_seen':None,'severity':'P3'}],[],'demo-user')
        rows[0]['state']='ACKNOWLEDGED'
        with patch.object(routes,'source',return_value=(rows,{},True)):
            result=routes.list_alarms(start='2026-10-28',end='2026-10-28',page=1,page_size=1,user=dict(id='demo-user',role='Gözlemci',is_demo=True))
        self.assertEqual(result['total'],1);self.assertFalse(result['can_ack']);self.assertEqual(result['summary']['critical'],1)
        with patch.object(routes,'source') as source:
            with self.assertRaises(HTTPException):routes.list_alarms(start='bad',page=1,page_size=25,user={})
            source.assert_not_called()

class MemorySQL:
    def __init__(self):self.actions={};self.requests={};self.queries=[];self.fail=False;self.available=True
    @contextmanager
    def begin(self):
        before=deepcopy((self.actions,self.requests))
        try:yield self
        except BaseException:self.actions,self.requests=before;raise
    def execute(self,statement,params=None):
        sql=str(statement);params=params or {};self.queries.append(sql)
        value=None;rows=[]
        if 'to_regclass' in sql:value='v2_demo.table' if self.available else None
        elif 'SELECT fingerprint,response' in sql:value=self.requests.get(params['id'])
        elif 'SELECT source_snapshot' in sql:value=next((row['source_snapshot'] for row in self.actions.values() if row['alarm_id']==params['alarm'] and row['occurrence_id']==params['occurrence']),None)
        elif 'SELECT payload' in sql:rows=[]
        elif 'INSERT INTO v2_demo.alarm_actions' in sql:
            key=tuple(params[k] for k in ('alarm','occurrence','action','owner'))
            if key not in self.actions:
                value=dict(id=params['id'],alarm_id=params['alarm'],occurrence_id=params['occurrence'],action=params['action'],actor_id=params['actor'],owner=params['owner'],source_snapshot=json.loads(params['snapshot']),occurred_at=AT)
                self.actions[key]=value
        elif 'SELECT * FROM v2_demo.alarm_actions' in sql:value=self.actions[tuple(params[k] for k in ('alarm','occurrence','action','owner'))]
        elif 'INSERT INTO v2_demo.alarm_requests' in sql:
            if self.fail:raise OperationalError('INSERT',{},Exception('synthetic failure'))
            self.requests[params['id']]=dict(fingerprint=params['fingerprint'],response=json.loads(params['response']))
        return SimpleNamespace(scalar_one=lambda:value,scalar_one_or_none=lambda:value,scalars=lambda:rows,mappings=lambda:SimpleNamespace(one_or_none=lambda:value,one=lambda:value))

class AlarmTransactionsTests(TestCase):
    def setUp(self):
        self.db=MemorySQL();self.adapter=SimpleNamespace(schema='v2_demo',engine=self.db,_verify=Mock())
        self.alarm={**record(),'id':identity(ROUTERS[0]['id'],'WAN_DOWN')}
        self.project=patch.object(storage,'project_alarms',return_value=([self.alarm],{}));self.project.start();self.addCleanup(self.project.stop)
    def action(self,id=None,kind='ACK',actor='demo-user',occurrence='demo-source-1'):
        return storage.mutate(self.adapter,self.alarm['id'],id or str(uuid4()),occurrence,kind,actor)
    def test_same_request_and_new_duplicate_ack_have_one_effect_and_original_actor_time(self):
        rid=str(uuid4());first=self.action(rid)
        self.assertEqual(first,self.action(rid));self.assertEqual(first,self.action(actor='demo-other'))
        self.assertEqual(len(self.db.actions),1);self.assertEqual(len(self.db.requests),2)
        self.assertEqual(first['action']['actor_id'],'demo-user')
    def test_request_id_reuse_conflicts_and_read_is_separate_per_user(self):
        rid=str(uuid4());self.action(rid)
        with self.assertRaises(DemoChangeError):self.action(rid,kind='READ')
        self.action(kind='READ');self.action(kind='READ');self.action(kind='READ',actor='demo-other')
        self.assertEqual(len(self.db.actions),3)
    def test_stale_occurrence_and_resolved_source_reject_without_audit(self):
        with self.assertRaises(DemoChangeError):self.action(occurrence='other')
        self.alarm['source_state']='RESOLVED'
        with self.assertRaises(DemoChangeError):self.action()
        self.assertEqual(self.db.actions,{})
    def test_failed_receipt_rolls_back_ack_and_serializes_source_and_action(self):
        self.db.fail=True
        with self.assertRaises(DemoStorageUnavailable):self.action()
        self.assertEqual(self.db.actions,{});self.assertEqual(self.db.requests,{})
        self.assertTrue(any('pg_advisory_xact_lock' in sql for sql in self.db.queries))
        self.assertIn('LOCK TABLE v2_demo.subscribers IN SHARE MODE',self.db.queries)

    def test_archived_notification_can_be_read_but_missing_source_cannot_be_acked(self):
        self.action()
        self.project.stop();self.project=patch.object(storage,'project_alarms',return_value=([],{}));self.project.start()
        with self.assertRaises(DemoChangeError):self.action()
        result=self.action(kind='READ')
        self.assertEqual(result['action']['action'],'READ')
        self.assertEqual(len(self.db.actions),2)

    def test_missing_action_schema_blocks_before_source_or_audit_writes(self):
        self.db.available=False
        with self.assertRaises(DemoChangeError) as failure:self.action()
        self.assertEqual(failure.exception.status_code,503)
        self.assertFalse(any('INSERT' in query or 'CREATE' in query for query in self.db.queries))

class AlarmSetupTests(TestCase):
    def test_explicit_fixture_uses_only_one_new_snapshot_and_preserves_seed_objects(self):
        from unittest.mock import MagicMock
        from app import demo_storage
        before=deepcopy(demo_storage.SUBSCRIBERS)
        engine=MagicMock();adapter=Mock()
        with patch('app.core.database.engine',engine),patch.object(demo_storage,'PostgresDemoStore',return_value=adapter),patch('app.adapters.alarm_actions.initialize') as setup,patch.object(demo_storage,'insert_snapshot') as insert:
            id=demo_storage.prepare_alarm_acceptance()
        setup.assert_called_once_with(adapter);insert.assert_called_once()
        snapshot=insert.call_args.args[2]
        self.assertEqual(snapshot['item']['id'],id);self.assertTrue(snapshot['item']['username'].startswith('alarm.accept.'))
        self.assertEqual(snapshot['history'],[])
        self.assertNotIn(id,{item['id'] for item in before});self.assertEqual(demo_storage.SUBSCRIBERS,before)

    def test_notification_write_requires_header_and_does_not_use_ack_permission(self):
        user=dict(id='demo-reader',is_demo=True,role='Gözlemci')
        body=routes.AlarmAction(request_id=uuid4(),occurrence_id='demo-source',confirmed=True)
        with patch.object(routes.demo_subscriptions,'store') as store:
            with self.assertRaises(HTTPException):routes.notification_read('demo-alarm-id',body,user,None)
            store.alarm_action.assert_not_called()
            routes.notification_read('demo-alarm-id',body,user,'alarm-read')
            self.assertEqual(store.alarm_action.call_args.args[-2:],('READ','demo-reader'))
