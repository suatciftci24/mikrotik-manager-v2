"""Synthetic state transitions and metadata transactions; no socket or live device."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest import TestCase
from app.schemas.demo_reports import DemoReport
from app.services.alarm_automation import process_report
from app.demo_storage import initialize_demo, seed_examples, process_demo_events
from test_demo_integration_seed import fake_engine, FakeConnection

NOW=datetime(2026,10,27,12,tzinfo=timezone.utc)
def observation(key,hour,status='ONLINE',interface='wan1',route='route1',**extra):
    return dict(id='demo-observation-'+key,router_id='demo-router-001',observed_at=f'2026-10-27T{hour}:00:00Z',scope='internet',source='synthetic-observation',internet_status=status,wan_interface=interface,default_route=route,is_demo=True,**extra)
def base():
    return DemoReport(subscriber_id='demo-sub-test',router_id='demo-router-001',recorded_at=NOW,is_demo=True)

class AlarmAutomation(TestCase):
    def test_open_close_and_duplicate_states_preserve_one_lifecycle(self):
        rows=[observation('a','08'),observation('b','09','OFFLINE'),observation('c','10','OFFLINE'),observation('d','11')]
        report=process_report(base(),rows,now=NOW)
        self.assertEqual([e.kind for e in report.router_events],['INTERNET_DOWN','INTERNET_UP'])
        down,up=report.router_events
        self.assertEqual(up.down_event_id,down.id);self.assertEqual(down.state,'RESOLVED')
        self.assertEqual((datetime.fromisoformat(up.occurred_at)-datetime.fromisoformat(down.occurred_at)).total_seconds(),7200)
        self.assertEqual(process_report(report,rows,now=NOW),report)
        self.assertEqual(process_report(report,now=NOW),report)

    def test_wan_interface_or_default_route_changes_create_one_event_each(self):
        rows=[observation('a','08'),observation('b','09',interface='wan2'),observation('c','10',interface='wan2'),observation('d','11',interface='wan2',route='route2')]
        events=process_report(base(),rows,now=NOW).router_events
        self.assertEqual([e.kind for e in events],['WAN_CHANGE','WAN_CHANGE'])
        self.assertEqual(events[0].previous_wan,'wan1 · route1');self.assertEqual(events[1].new_wan,'wan2 · route2')

    def test_missing_data_never_opens_an_outage_or_wan_change(self):
        report=process_report(base(),[observation('a','08'),observation('b','09',None,None,None),observation('c','10','OFFLINE','wan2','route2')],now=NOW)
        self.assertEqual(report.router_events,[])
        # First OFFLINE is only a baseline; recovery start is not fabricated.
        report=process_report(base(),[observation('a','08','OFFLINE'),observation('b','09')],now=NOW)
        self.assertEqual([e.kind for e in report.router_events],['INTERNET_UP']);self.assertIsNone(report.router_events[0].down_event_id)

    def test_missing_during_open_outage_is_unknown_and_duration_stays_unverified(self):
        opened=process_report(base(),[observation('a','08'),observation('b','09','OFFLINE')],now=NOW)
        unknown=process_report(opened,[observation('c','10','UNKNOWN')],now=NOW)
        self.assertEqual(unknown.router_events[0].state,'UNKNOWN');self.assertFalse(unknown.router_events[0].duration_verified)
        closed=process_report(unknown,[observation('d','11')],now=NOW)
        self.assertEqual(closed.router_events[0].state,'RESOLVED');self.assertFalse(closed.router_events[0].duration_verified)
        self.assertEqual(closed.router_events[1].down_event_id,opened.router_events[0].id)
        self.assertEqual(len(closed.router_observations),4)

    def test_late_conflicting_non_demo_naive_and_future_measurements_fail_without_mutation(self):
        report=process_report(base(),[observation('a','08')],now=NOW);before=deepcopy(report)
        from pydantic import ValidationError
        invalid=[{**observation('a','08'),'internet_status':'OFFLINE'},observation('late','07'),{**observation('x','09'),'is_demo':False},{**observation('x','09'),'observed_at':'2026-10-27T09:00:00'},observation('future','13'),{**observation('x','09'),'router_id':'demo-router-other'},{**observation('x','09'),'scope':'management'},{**observation('x','09'),'source':'routeros-live'}]
        for raw in invalid:
            with self.subTest(raw=raw),self.assertRaises((ValueError,ValidationError)):
                process_report(report,[raw],now=NOW)
        self.assertEqual(report,before)

    def test_timezone_offsets_and_input_order_have_stable_event_identity(self):
        a=observation('a','08');b=observation('b','09','OFFLINE');b['observed_at']='2026-10-27T12:00:00+03:00'
        left=process_report(base(),[a,b],now=NOW);right=process_report(base(),[b,a],now=NOW)
        self.assertEqual(left,right);self.assertEqual(left.router_events[0].occurred_at,'2026-10-27T09:00:00+00:00')

    def test_seed_and_metadata_processing_leave_user_records_and_account_history_unchanged(self):
        engine,connection=fake_engine();initialize_demo(engine);seed_examples(engine)
        before=deepcopy((connection.items,connection.events,connection.requests))
        self.assertEqual(process_demo_events(engine),0)
        self.assertEqual((connection.items,connection.events,connection.requests),before)
        self.assertEqual(seed_examples(engine),0)
        self.assertEqual((connection.items,connection.events,connection.requests),before)

    def test_append_transaction_keeps_history_and_retry_does_not_write_twice(self):
        import json
        engine,connection=fake_engine();initialize_demo(engine);seed_examples(engine)
        item=next(item for item in connection.items.values() if item.get('router_id')=='demo-router-001')
        before=deepcopy(item)
        saved_events=deepcopy(connection.events);saved_requests=deepcopy(connection.requests)
        original=connection.execute
        writes=[]
        def execute(sql,params=None):
            if str(sql).startswith('UPDATE v2_demo.subscribers SET payload='):
                writes.append(params['id']);connection.items[params['id']]=json.loads(params['payload'])
            return original(sql,params)
        connection.execute=execute
        row=dict(id='demo-observation-appended',router_id='demo-router-001',observed_at=datetime.now(timezone.utc).isoformat(),scope='internet',source='synthetic-observation',internet_status='OFFLINE',wan_interface='wan2',default_route='0.0.0.0/0 via 192.0.2.101',is_demo=True)
        batches=[{'subscriber_id':item['id'],'observations':[row]}]
        self.assertEqual(process_demo_events(engine,batches),1)
        after=connection.items[item['id']]
        self.assertEqual(after['revision'],before['revision']);self.assertEqual(after['demo_report']['recorded_at'],before['demo_report']['recorded_at'])
        self.assertEqual({event['id'] for event in after['demo_report']['router_events']},{event['id'] for event in before['demo_report']['router_events']}|{after['demo_report']['router_events'][-1]['id']})
        self.assertEqual(len(after['demo_report']['router_events']),len(before['demo_report']['router_events'])+1)
        self.assertEqual(process_demo_events(engine,batches),0);self.assertEqual(len(writes),1)
        self.assertEqual(connection.events,saved_events);self.assertEqual(connection.requests,saved_requests)

    def test_legacy_history_is_preserved_and_same_time_conflicts_are_rejected(self):
        from app.schemas.router_events import RouterEvent
        report=base().model_copy(update={'router_events':[RouterEvent(id='demo-legacy',router_id='demo-router-001',kind='WAN_CHANGE',occurred_at='2026-10-26T09:00:00Z',is_demo=True)]})
        processed=process_report(report,[observation('a','08'),observation('b','09','OFFLINE')],now=NOW)
        self.assertEqual(processed.router_events[0],report.router_events[0]);self.assertEqual(len(processed.router_events),2)
        with self.assertRaises(ValueError):
            process_report(base(),[observation('a','08'),observation('b','08','OFFLINE')],now=NOW)

    def test_turkey_midnight_does_not_shift_utc_duration_evidence(self):
        rows=[{**observation('a','08'),'observed_at':'2026-10-26T20:55:00Z'},
              {**observation('b','09','OFFLINE'),'observed_at':'2026-10-26T23:59:00+03:00'},
              {**observation('c','10'),'observed_at':'2026-10-27T00:01:00+03:00'}]
        report=process_report(base(),rows,now=NOW);down,up=report.router_events
        self.assertEqual(down.occurred_at,'2026-10-26T20:59:00+00:00')
        self.assertEqual((datetime.fromisoformat(up.occurred_at)-datetime.fromisoformat(down.occurred_at)).total_seconds(),120)

    def test_invalid_batch_or_duplicate_router_owner_never_partially_writes(self):
        engine,connection=fake_engine();initialize_demo(engine);seed_examples(engine)
        before=deepcopy(connection.items)
        with self.assertRaises(ValueError):
            process_demo_events(engine,[{'subscriber_id':'demo-sub-missing','observations':[]}])
        self.assertEqual(connection.items,before)
        owner=next(item for item in connection.items.values() if item.get('router_id')=='demo-router-001')
        duplicate=deepcopy(owner);duplicate['id']='demo-sub-other-owner';duplicate['demo_report']['subscriber_id']=duplicate['id']
        connection.items[duplicate['id']]=duplicate
        writes=[];original=connection.execute
        def execute(sql,params=None):
            if str(sql).startswith('UPDATE '):writes.append(params)
            return original(sql,params)
        connection.execute=execute
        with self.assertRaises(ValueError):process_demo_events(engine)
        self.assertEqual(writes,[])
