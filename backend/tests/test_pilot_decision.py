"""Pure/scoped review decisions, never executing pilots or changing business data."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.integrations import pilot_decision as service,planning
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS

class PilotDecisionTests(TestCase):
    def setUp(self):
        self.user=public_user(bootstrap());self.id=ROUTERS[0]['id'];self.read=patch.object(service,'read_report',return_value={'items':[],'status':'DISABLED'});self.read.start();self.addCleanup(self.read.stop)
    def test_readiness_checks_separate_measured_synthetic_conditions_from_unknown_real_conditions(self):
        result=service.assessment(self.user,self.id);checks={c['id']:c for c in result['checklist']}
        self.assertEqual(checks['IDENTITY_MAPPING']['status'],'PASS');self.assertEqual(checks['REQUEST_AUTHORIZATION']['status'],'PASS')
        for id in ['SOURCE_VALIDATION','FRESHNESS','PILOT_SCOPE','TIMEBOX','ACCESS_LIMIT','ROLLBACK_REHEARSAL']:self.assertEqual(checks[id]['status'],'UNKNOWN')
        self.assertEqual(checks['ADMIN_APPROVAL']['status'],'BLOCKED');self.assertEqual(result['decision'],'REVIEW_REQUIRED');self.assertFalse(result['execution_authorized'])
    def test_eligible_for_review_is_not_go_even_without_approval_or_live_evidence(self):
        result=service.assessment(self.user,ROUTERS[-1]['id']);self.assertEqual(result['decision'],'ELIGIBLE_FOR_REVIEW');self.assertEqual(result['approval'],'APPROVAL REQUIRED');self.assertFalse(result['execution_authorized']);self.assertFalse(result['external_writes']);self.assertIn('APPROVAL_ABSENT',result['decision_reasons'])
    def test_backend_mismatch_and_profile_missing_produce_no_go(self):
        result=service.assessment(self.user,ROUTERS[1]['id']);self.assertEqual(result['decision'],'NO_GO');codes={r['code'] for r in result['risks']};self.assertIn('BACKEND_MISMATCH',codes);self.assertIn('PROFILE_MAPPING_MISSING',codes)
    def test_no_mapping_evidence_is_unknown_and_cannot_be_eligible(self):
        result=service.assessment(self.user,ROUTERS[2]['id']);self.assertEqual(result['decision'],'REVIEW_REQUIRED');self.assertTrue(all(c['status']=='UNKNOWN' for c in result['comparison']))
    def test_comparison_covers_router_account_profile_expire_sessions_and_audit(self):
        result=service.assessment(self.user,self.id);self.assertEqual({c['id'] for c in result['comparison']},{'ROUTER_IDENTITY','PPPOE_ACCOUNT','PROFILE','EXPIRE','SESSION','AUDIT'})
        self.assertEqual(next(c for c in result['comparison'] if c['id']=='SESSION')['status'],'WARNING')
        self.assertTrue(all(c['source']=='STAGE19_SYNTHETIC_MAPPING' for c in result['comparison']))
    def test_risk_order_and_reasons_and_hash_are_deterministic(self):
        first=service.assessment(self.user,ROUTERS[1]['id']);second=service.assessment(self.user,ROUTERS[1]['id']);self.assertEqual(first,second)
        keys=[(r['severity'],r['code'],r['criterion']) for r in first['risks']];self.assertEqual(keys,sorted(keys));self.assertEqual(len(first['evidence_hash']),64)
        self.assertEqual(len(first['decision_reasons']),len(set(first['decision_reasons'])))
    def test_collision_is_high_priority_and_isolation_contradiction_is_fail_closed(self):
        detail=planning.detail(self.user,self.id);detail['item']['mapping']['issues']=['ACCOUNT_TARGET_COLLISION'];detail['item']['mapping']['result']='BLOCKED'
        result=service._evaluate(detail,{});self.assertEqual(result['decision'],'NO_GO');self.assertEqual(result['risks'][0]['severity'],'P1')
        detail=planning.detail(self.user,self.id);detail['item']['routeros_enabled']=True;result=service._evaluate(detail,{});self.assertEqual(result['decision'],'NO_GO');self.assertEqual(result['connection'],'UNKNOWN');self.assertFalse(result['execution_authorized'])
    def test_unrecognized_mapping_failure_does_not_fall_through_to_review_eligibility(self):
        detail=planning.detail(self.user,ROUTERS[-1]['id']);detail['item']['mapping']['result']='BLOCKED';detail['item']['mapping']['issues']=['NEW_CONTRACT_FAILURE'];self.assertEqual(service._evaluate(detail,{})['decision'],'NO_GO')
    def test_missing_audit_and_expiry_evidence_is_not_pass(self):
        detail=planning.detail(self.user,self.id);detail['item']['mapping']['counts']['audits']=0;detail['item']['mapping']['issues']=['EXPIRY_DECISION_MISSING'];detail['item']['mapping']['result']='BLOCKED'
        result=service._evaluate(detail,{});self.assertEqual(next(c for c in result['comparison'] if c['id']=='AUDIT')['status'],'UNKNOWN');self.assertEqual(next(c for c in result['comparison'] if c['id']=='EXPIRE')['status'],'BLOCKED')
    def test_simulator_artifact_is_scoped_and_never_real_freshness_proof(self):
        report={'items':[{'owner_router_id':self.id}],'last_run':'recorded-synthetic-run'}
        result=service.assessment(self.user,self.id,report);self.assertEqual(next(c for c in result['checklist'] if c['id']=='SIMULATOR')['status'],'WARNING');self.assertEqual(next(c for c in result['checklist'] if c['id']=='FRESHNESS')['status'],'UNKNOWN');self.assertEqual(result['simulation_run'],'recorded-synthetic-run')
        self.assertIsNone(service.assessment(self.user,ROUTERS[-1]['id'],report)['simulation_run'])
    def test_scope_precedes_plan_and_artifact_reads_and_filters_totals(self):
        scoped={**self.user,'permissions':{self.id:{'can_view':True,'can_view_reports':True}}}
        with patch.object(planning,'detail',wraps=planning.detail) as detail:
            result=service.inventory(scoped,page_size=1);self.assertEqual(result['total'],1);self.assertEqual(result['items'][0]['router_id'],self.id);detail.assert_called_once_with(scoped,self.id)
        with patch.object(service,'read_report') as artifact:
            self.assertEqual(service.inventory({**self.user,'permissions':{}})['total'],0);artifact.assert_not_called()
    def test_hidden_router_404_visible_report_denied_403_before_evidence(self):
        for user,code in [({**self.user,'permissions':{}},404),({**self.user,'permissions':{self.id:{'can_view':True}}},403)]:
            with patch.object(planning,'detail') as detail:
                with self.assertRaises(HTTPException) as error:service.assessment(user,self.id)
                self.assertEqual(error.exception.status_code,code);detail.assert_not_called()
    def test_corrupt_fixture_is_no_go_and_error_secrets_not_reflected(self):
        with patch.object(planning,'fixture_for',side_effect=ValueError('secretref:v2/private/key')):result=service.assessment(self.user,self.id)
        self.assertEqual(result['decision'],'NO_GO');self.assertNotIn('private',str(result));self.assertNotIn('secretref:',str(result))
    def test_api_is_admin_readonly_and_viewer_rejected(self):
        from app.api.v1.system import router
        from app.core.security import current_admin
        routes=[r for r in router.routes if r.path.startswith('/system/pilot-decisions')];self.assertEqual(len(routes),2)
        for route in routes:self.assertEqual(route.methods,{'GET'});self.assertIn(current_admin,[d.call for d in route.dependant.dependencies])
        for user in [dict(is_demo=True,role_code='VIEWER'),dict(is_demo=True,role_code='ADMIN',can_manage_users=False)]:
            with self.assertRaises(HTTPException):current_admin(user)
    def test_reading_is_side_effect_free_and_out_of_range_page_has_no_records(self):
        before=deepcopy(ROUTERS);first=service.inventory(self.user,page=999,page_size=1);self.assertEqual(first['total'],len(ROUTERS));self.assertEqual(first['items'],[]);self.assertEqual(ROUTERS,before)
    def test_evidence_hash_binds_mapping_values_even_when_comparison_status_stays_same(self):
        from datetime import date
        first=service.assessment(self.user,self.id);fixture,review=planning.fixture_for(self.id)
        account=fixture.accounts[0].model_copy(update={'expiry_mode':'DATE','expires_on':date(2027,1,1)})
        with patch.object(planning,'fixture_for',return_value=(fixture.model_copy(update={'accounts':(account,)}),review)):second=service.assessment(self.user,self.id)
        self.assertEqual(first['comparison'],second['comparison']);self.assertNotEqual(first['mapping_evidence_hash'],second['mapping_evidence_hash']);self.assertNotEqual(first['evidence_hash'],second['evidence_hash'])
