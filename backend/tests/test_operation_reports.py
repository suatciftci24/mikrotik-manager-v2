from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.services.operation_reports import report_range, in_range, connection_records, project_report
from app.schemas.router_events import RouterEventList
from app.api.v1 import reports
from app.core.security import current_demo_user
from app.main import app
from app.services.demo_data import ROUTERS

class ReportsTests(TestCase):
    now=datetime(2026,10,28,12,tzinfo=timezone.utc)
    def test_turkey_boundaries_future_and_invalid_ranges(self):
        bounds=report_range('2026-10-28','2026-10-28',self.now)
        self.assertTrue(in_range('2026-10-27T21:00:00Z',bounds))
        self.assertFalse(in_range('2026-10-27T20:59:59Z',bounds))
        self.assertFalse(in_range('2026-10-28T21:00:00Z',bounds))
        self.assertFalse(in_range('2026-10-28T12:00:01Z',bounds))
        for first,last in [('2026-10-29','2026-10-28'),('2025-01-01','2026-10-28'),('2026-02-30','2026-10-28')]:
            with self.assertRaises(ValueError):report_range(first,last,self.now)

    def events(self,verified=True,up_router=None):
        rid=ROUTERS[0]['id']
        return RouterEventList(available=True,items=[dict(id='demo-down',router_id=rid,kind='INTERNET_DOWN',occurred_at='2026-10-28T09:00:00Z',state='OPEN',duration_verified=verified,is_demo=True),dict(id='demo-up',router_id=up_router or rid,kind='INTERNET_UP',down_event_id='demo-down',occurred_at='2026-10-28T09:05:00Z',is_demo=True)])

    def test_recovery_once_with_verified_duration(self):
        rows=connection_records(self.events())
        self.assertEqual(len(rows),2)
        self.assertEqual([row['kind'] for row in rows],['INTERNET_DOWN','INTERNET_UP'])
        self.assertEqual(rows[0]['lifecycle']['duration_seconds'],300)
        self.assertEqual(rows[1]['lifecycle']['recovery_id'],'demo-up')

    def test_missing_or_conflicting_time_never_invents_duration(self):
        self.assertIsNone(connection_records(self.events(False))[0]['lifecycle']['duration_seconds'])
        self.assertIsNone(connection_records(self.events(up_router='demo-router-other'))[0]['lifecycle']['ended_at'])
        self.assertIsNone(connection_records(RouterEventList()))
        source=self.events();source.items[0].occurred_at=None
        self.assertIsNone(connection_records(source)[0]['lifecycle']['ended_at'])

    def test_snapshot_counts_are_separate_from_unknown_failures_and_paged_events(self):
        bounds=report_range('2026-10-28','2026-10-28',self.now)
        empty=SimpleNamespace(events=[])
        with patch('app.services.operation_reports.analyze',return_value=empty),patch('app.services.operation_reports.project_saved',return_value=[]),patch('app.services.operation_reports.router_event_records',return_value=self.events()):
            data=project_report([],ROUTERS,[],0,[dict(operation='STATUS_CHANGE',status='PAUSED',total=2)],bounds,'CONNECTION','', 'ALL','ALL',2,1)
        self.assertEqual(data['total'],2);self.assertEqual(len(data['items']),1)
        self.assertEqual(data['summary']['deactivated'],2)
        self.assertIsNone(data['summary']['failures'])
        self.assertEqual(data['summary']['open_events'],0)

    def test_route_rejects_bad_dates_and_router_before_store_access(self):
        with patch.object(reports.demo_subscriptions,'store') as store:
            with self.assertRaises(HTTPException):reports.operations('bad','2026-10-28')
            with self.assertRaises(HTTPException):reports.operations('2026-10-28','2026-10-28',router_id='foreign')
            store.report_records.assert_not_called()

    def test_report_route_is_authenticated_get_and_bounds_page_size(self):
        route=next(r for r in reports.router.routes if getattr(r,'path','')=='/reports/operations')
        self.assertEqual(route.methods,{'GET'})
        self.assertIn(current_demo_user,[dep.call for dep in route.dependant.dependencies])
        schema=app.openapi()['paths']['/api/v1/reports/operations']['get']['parameters']
        size=next(p['schema'] for p in schema if p['name']=='page_size')
        self.assertEqual(size['maximum'],50);self.assertEqual(size['minimum'],1)

    def test_page_and_filters_reach_storage_without_unbounded_audit_fetch(self):
        with patch.object(reports.demo_subscriptions,'store') as store,patch.object(reports,'project_report',return_value={}) as project:
            store.report_records.return_value=([],[],0,[])
            reports.operations('2026-10-28','2026-10-28',router_id=ROUTERS[0]['id'],operation='STATUS_CHANGE',page=3,page_size=25)
            args=store.report_records.call_args.args
            self.assertEqual(args[-3:],('STATUS_CHANGE',25,50))
            self.assertEqual(args[3],ROUTERS[0]['id']);project.assert_called_once()

    def test_sql_reader_uses_readonly_snapshot_and_database_page_bounds(self):
        from unittest.mock import MagicMock
        from app.adapters.demo_subscriptions import PostgresDemoStore
        from sqlalchemy.engine import make_url
        engine=MagicMock();engine.url=make_url('postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2')
        adapter=PostgresDemoStore(engine)
        connection=engine.connect.return_value.execution_options.return_value.__enter__.return_value
        connection.execute.return_value.scalars.return_value=[]
        connection.execute.return_value.mappings.return_value=[]
        connection.execute.return_value.scalar_one.return_value=0
        with patch.object(adapter,'_verify') as verify:
            result=adapter.report_records(*report_range('2026-10-28','2026-10-28',self.now),'','','','',25,50)
        verify.assert_called_once_with(connection)
        queries=[str(call.args[0]) for call in connection.execute.call_args_list]
        self.assertEqual(queries[0],'SET TRANSACTION READ ONLY')
        self.assertIn('LIMIT :limit OFFSET :offset',queries[-1])
        self.assertIn('JOIN v2_demo.subscribers',queries[-1])
        self.assertEqual(connection.execute.call_args.args[1]['offset'],50)
        self.assertEqual(result[2],0)

    def test_recovery_in_range_is_not_lost_when_outage_started_yesterday(self):
        source=self.events();source.items[0].occurred_at='2026-10-27T20:55:00Z';source.items[1].occurred_at='2026-10-27T21:05:00Z'
        bounds=report_range('2026-10-28','2026-10-28',self.now)
        scoped=[row for row in connection_records(source) if in_range(row['occurred_at'],bounds)]
        self.assertEqual([row['kind'] for row in scoped],['INTERNET_UP'])
        self.assertEqual(scoped[0]['lifecycle']['duration_seconds'],600)

    def test_saved_synthetic_source_and_mika_transition_scope_are_reused(self):
        from app.services.demo_examples import demo_examples
        items=[row['item'] for row in demo_examples(self.now)]
        bounds=report_range('2026-10-01','2026-10-28',self.now)
        data=project_report(items,ROUTERS,[],0,[],bounds,'MIKA','','P2','ALL',1,25)
        self.assertTrue(data['is_demo']);self.assertTrue(data['read_only'])
        self.assertTrue(all(event['priority']=='P2' for event in data['items']))
        self.assertLessEqual(len(data['items']),25)
        self.assertGreater(data['summary']['subscribers'],0)
