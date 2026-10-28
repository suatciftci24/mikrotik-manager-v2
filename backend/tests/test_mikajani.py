"""Pure analysis/source/authorization contracts; no DB, ASGI transport or live devices."""
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.schemas.mikajani import Observation, Analysis
from app.services.mikajani import analyze
from app.services.mikajani_sources import scenario_analysis, SCENARIOS, project_saved
from app.services.demo_data import ROUTERS
from app.services.demo_subscriptions import DemoStorageUnavailable
from app.api.v1 import mikajani
from app.main import app
from app.core.security import current_demo_user


class MikaAnalysisTests(TestCase):
    def setUp(self):
        self.at=datetime(2026,10,28,9,tzinfo=timezone.utc)
        self.routers=ROUTERS[:2]

    def observation(self, second=0, status='BAD', domain='WAN', evidence='WAN down', router=0, subject=None):
        return Observation(id=f'demo-test-{router}-{domain}-{second}-{subject}',router_id=self.routers[router]['id'],
            domain=domain,status=status,observed_at=self.at+timedelta(seconds=second),evidence=evidence,subject_id=subject)

    def run_analysis(self,rows,seconds=300):
        return analyze(self.routers,rows,self.at+timedelta(seconds=seconds))

    def test_all_seven_scenarios_and_deterministic_replay(self):
        self.assertEqual(len(SCENARIOS),7)
        for key in SCENARIOS:
            first=scenario_analysis(key);second=scenario_analysis(key)
            self.assertEqual(first.model_dump(exclude={'generated_at'}),second.model_dump(exclude={'generated_at'}))
            Analysis.model_validate(first.model_dump())
            self.assertTrue(first.read_only)
        for key,domain in [('wan','WAN'),('ipsec','IPSEC'),('router','ROUTER'),('pppoe','PPPOE'),('central','CORRELATION')]:
            self.assertTrue(any(e.domain==domain for e in scenario_analysis(key).events))
        self.assertTrue(any(h.reliability=='STALE' for h in scenario_analysis('uncertain').health))

    def test_lifecycle_repeated_bad_recovery_and_resolved_episode(self):
        rows=[self.observation(),self.observation(10),self.observation(20,evidence='WAN route changed'),
              self.observation(30,'GOOD',evidence='up'),self.observation(40,'GOOD',evidence='up'),
              self.observation(95,'GOOD',evidence='up'),self.observation(120,evidence='second outage')]
        events=[e for e in self.run_analysis(rows).events if e.domain=='WAN']
        self.assertEqual(len(events),2)
        resolved=next(e for e in events if e.state=='RESOLVED')
        self.assertEqual([h.state for h in resolved.history],['OPEN','UPDATED','RECOVERING','RESOLVED'])
        self.assertNotEqual(events[0].id,events[1].id)
        duplicate=self.run_analysis(rows+rows)
        self.assertEqual([e.model_dump() for e in duplicate.events],[e.model_dump() for e in self.run_analysis(rows).events])

    def test_unknown_interrupts_recovery_and_missing_never_means_healthy(self):
        rows=[self.observation(),self.observation(20,'GOOD'),self.observation(90,'UNKNOWN',evidence='lost evidence')]
        result=self.run_analysis(rows)
        event=next(e for e in result.events if e.domain=='WAN')
        self.assertEqual(event.state,'UPDATED');self.assertEqual(event.confidence,'LOW')
        self.assertIsNone(event.resolved_at)
        empty=self.run_analysis([])
        self.assertTrue(all(h.health=='UNKNOWN' and h.reliability=='MISSING' for h in empty.health))
        self.assertEqual(empty.health[0].signals['IPSEC'],'UNKNOWN')

    def test_freshness_replay_is_independent_of_read_frequency(self):
        row=self.observation(status='GOOD')
        first=self.run_analysis([row],1200);later=self.run_analysis([row],1500)
        self.assertEqual([e.model_dump() for e in first.events],[e.model_dump() for e in later.events])
        self.assertEqual(first.health[0].signals['WAN'],'UNKNOWN')
        self.assertEqual(first.events[0].priority,'P4')

    def test_correlation_requires_multiple_recent_routers_and_is_tentative(self):
        first=self.observation(domain='ROUTER')
        self.assertFalse(any(e.domain=='CORRELATION' for e in self.run_analysis([first]).events))
        late=self.observation(180,domain='ROUTER',router=1)
        self.assertFalse(any(e.domain=='CORRELATION' for e in self.run_analysis([first,late]).events))
        close=self.observation(90,domain='ROUTER',router=1)
        event=next(e for e in self.run_analysis([first,close]).events if e.domain=='CORRELATION')
        self.assertEqual(event.confidence,'LOW');self.assertEqual(event.priority,'P1')
        self.assertEqual(len(event.affected_router_ids),2);self.assertIn('kesin',event.reason)

    def test_pppoe_other_subscriber_good_cannot_resolve_anomaly(self):
        result=self.run_analysis([self.observation(domain='PPPOE',subject='demo-sub-a'),
            self.observation(80,'GOOD','PPPOE',subject='demo-sub-b'),self.observation(160,'GOOD','PPPOE',subject='demo-sub-b')])
        event=next(e for e in result.events if e.domain=='PPPOE')
        self.assertEqual(event.state,'OPEN');self.assertEqual(result.health[0].signals['PPPOE'],'BAD')

    def test_rejects_future_unknown_router_real_data_and_conflicting_evidence(self):
        row=self.observation()
        for rows in [[self.observation(1000)],[row.model_copy(update={'router_id':'unknown'})],
                     [row,row.model_copy(update={'evidence':'rewritten'})],
                     [row,row.model_copy(update={'id':'different','status':'GOOD'})]]:
            with self.assertRaises(ValueError):self.run_analysis(rows)
        with self.assertRaises(ValueError):analyze([{**ROUTERS[0],'is_demo':False}],[],self.at)
        with self.assertRaises(ValueError):self.run_analysis([row.model_dump()|{'is_demo':False}])

    def test_saved_projection_preserves_router_time_and_has_no_invented_ipsec(self):
        rows=project_saved(self.routers,[])
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r.domain=='ROUTER' for r in rows))
        self.assertEqual(rows[0].observed_at.isoformat(),self.routers[0]['last_seen'])

    def test_api_routes_get_only_protected_and_failed_saved_source_is_not_scenario(self):
        routes=[r for r in app.routes if getattr(r,'path','').startswith('/api/v1/mikajani')]
        # Some FastAPI releases expose nested include routers; verify the concrete feature router too.
        routes=list(mikajani.router.routes)
        self.assertEqual(len(routes),7)
        self.assertTrue(all(r.methods=={'GET'} for r in routes))
        self.assertTrue(all(any(d.call is current_demo_user for d in r.dependant.dependencies) for r in routes))
        with self.assertRaises(HTTPException) as failure:current_demo_user(None)
        self.assertEqual(failure.exception.status_code,401)
        with patch('app.services.demo_subscriptions.store') as store:
            store.list_items.side_effect=DemoStorageUnavailable()
            with self.assertRaises(HTTPException) as failure:mikajani.analysis(None)
            self.assertEqual(failure.exception.status_code,503)
            scenario=mikajani.analysis('ipsec')
            self.assertEqual(scenario.source,'scenario:ipsec')
            store.list_items.assert_called_once()
        with self.assertRaises(HTTPException):mikajani.analysis('invalid')
        self.assertTrue(all(e.state!='RESOLVED' for e in mikajani.events(scenario)))
        self.assertEqual(mikajani.history(scenario),scenario.events)
        self.assertEqual(mikajani.recommendations(scenario),mikajani.events(scenario))

    def test_saved_session_projection_does_not_mix_subscriber_evidence(self):
        from app.services.demo_data import SUBSCRIBERS
        items=[]
        for index,count in enumerate((2,1)):
            item={**SUBSCRIBERS[index], 'router_id':self.routers[0]['id'], 'router_name':self.routers[0]['name']}
            item['demo_report']={'subscriber_id':item['id'],'router_id':item['router_id'],
                'recorded_at':self.at.isoformat(),'is_demo':True,
                'sessions':[{'id':f'demo-session-{index}-{n}', 'started_at':(self.at-timedelta(minutes=5)).isoformat(),
                             'state':'ACTIVE','is_demo':True} for n in range(count)]}
            items.append(item)
        observations=project_saved(self.routers,items)
        result=self.run_analysis(observations)
        self.assertEqual(len([e for e in result.events if e.domain=='PPPOE']),1)
        event=next(e for e in result.events if e.domain=='PPPOE')
        self.assertIn(items[0]['id'],event.evidence)
        self.assertNotIn(items[1]['id'],event.evidence)
        self.assertEqual(result.health[0].signals['PPPOE'],'BAD')

    def test_saved_wan_change_and_missing_ipsec_are_explicit(self):
        from app.services.demo_data import SUBSCRIBERS
        item={**SUBSCRIBERS[0], 'router_id':self.routers[0]['id']}
        item['demo_report']={'subscriber_id':item['id'],'router_id':item['router_id'],
            'recorded_at':self.at.isoformat(),'is_demo':True,
            'router_observations':[{'id':f'demo-wan-{n}', 'router_id':item['router_id'],
                'observed_at':(self.at+timedelta(seconds=n*60)).isoformat(), 'scope':'internet',
                'source':'synthetic-observation','internet_status':'ONLINE','wan_interface':wan,
                'default_route':'demo-route', 'is_demo':True} for n,wan in enumerate(('demo-wan-a','demo-wan-b'))]}
        result=self.run_analysis(project_saved(self.routers,[item]))
        event=next(e for e in result.events if e.domain=='WAN')
        self.assertIn('WAN değişti',event.evidence)
        self.assertEqual(result.health[0].signals['IPSEC'],'UNKNOWN')
        self.assertFalse(any(e.domain=='IPSEC' for e in result.events))

    def test_registered_openapi_paths_and_analysis_contract(self):
        paths=app.openapi()['paths']
        for suffix in ('analysis','health','events','history','summary','recommendations','scenarios'):
            path='/api/v1/mikajani/'+suffix
            self.assertIn(path,paths)
            self.assertEqual(set(paths[path]),{'get'})
        self.assertEqual(paths['/api/v1/mikajani/analysis']['get']['responses']['200']['content']['application/json']['schema']['$ref'],
                         '#/components/schemas/Analysis')
