"""Synthetic mapping review only; no V1/V2 DB or network reads/writes."""
from copy import deepcopy
from datetime import date,datetime,timezone
from unittest import TestCase
from unittest.mock import patch
from pydantic import ValidationError
from fastapi import HTTPException
from app.integrations import planning as service
from app.services.identity import bootstrap,public_user
from app.services.demo_data import ROUTERS
from app.integrations.contracts import Backend

class PlanningTests(TestCase):
    def setUp(self):self.user=public_user(bootstrap());self.id=ROUTERS[0]['id'];self.fixture,_=service.fixture_for(self.id)
    def mapping(self,**changes):return self.fixture.model_copy(update=changes)
    def test_inventory_has_all_four_preparation_states_without_connection_or_permission(self):
        response=service.inventory(self.user);self.assertEqual(response['total'],len(ROUTERS));self.assertEqual({r['preparation'] for r in response['items']},{'DEMO_ONLY','BLOCKED','READY_FOR_REVIEW','APPROVAL_REQUIRED'})
        self.assertTrue(all(r['connection']=='NOT CONNECTED' and not r['execution_authorized'] and not r['routeros_enabled'] and not r['radius_enabled'] and not r['external_writes'] for r in response['items']))
    def test_valid_fixture_checks_all_domains_without_fabricating_session_times(self):
        result=service.validate_mapping(self.fixture);self.assertEqual(result['result'],'VALIDATED_SYNTHETIC');self.assertEqual(result['counts'],dict(routers=1,accounts=1,sessions=1,audits=1));self.assertEqual(result['unknown_session_times'],1)
        self.assertEqual(service.validate_mapping(self.fixture),result)
    def test_source_and_target_router_collision(self):
        result=service.validate_mapping(self.mapping(routers=self.fixture.routers*2))
        for code in ['ROUTER_SOURCE_COLLISION','ROUTER_TARGET_COLLISION','MANAGEMENT_IDENTITY_COLLISION']:self.assertIn(code,result['issues'])
    def test_account_identity_and_username_collisions(self):
        result=service.validate_mapping(self.mapping(accounts=self.fixture.accounts*2))
        for code in ['ACCOUNT_SOURCE_COLLISION','ACCOUNT_TARGET_COLLISION','ACCOUNT_USERNAME_COLLISION']:self.assertIn(code,result['issues'])
    def test_missing_fields_and_backend_mismatch_are_blockers(self):
        account=self.fixture.accounts[0].model_copy(update={'username':None,'target_backend':Backend.RADIUS,'target_profile':None,'expiry_mode':'UNKNOWN'})
        result=service.validate_mapping(self.mapping(accounts=(account,)))
        for code in ['USERNAME_MISSING','BACKEND_MISMATCH','PROFILE_MAPPING_MISSING','EXPIRY_DECISION_MISSING']:self.assertIn(code,result['issues'])
        self.assertEqual(result['result'],'BLOCKED')
    def test_unknown_authority_and_unknown_router_are_not_guessed(self):
        account=self.fixture.accounts[0].model_copy(update={'backend':None,'legacy_router':'unmapped'})
        result=service.validate_mapping(self.mapping(accounts=(account,)));self.assertIn('BACKEND_MISSING',result['issues']);self.assertIn('ACCOUNT_ROUTER_MISSING',result['issues'])
        router=self.fixture.routers[0].model_copy(update={'target_id':'unmapped','management_identity':None})
        result=service.validate_mapping(self.mapping(routers=(router,)));self.assertIn('ROUTER_TARGET_UNKNOWN',result['issues']);self.assertIn('MANAGEMENT_IDENTITY_MISSING',result['issues'])
    def test_expiry_date_unlimited_and_unknown_are_distinct(self):
        account=self.fixture.accounts[0]
        dated=account.model_copy(update={'expiry_mode':'DATE','expires_on':date(2026,11,1)})
        self.assertEqual(service.validate_mapping(self.mapping(accounts=(dated,)))['issues'],[])
        for bad,code in [(dated.model_copy(update={'expires_on':None}),'EXPIRY_DECISION_MISSING'),(dated.model_copy(update={'expiry_mode':'UNLIMITED'}),'EXPIRY_CONFLICT')]:self.assertIn(code,service.validate_mapping(self.mapping(accounts=(bad,)))['issues'])
    def test_session_and_audit_lineage_missing_or_invalid_block_review(self):
        session=self.fixture.sessions[0].model_copy(update={'account_key':'missing','ended_at':datetime(2026,10,28,tzinfo=timezone.utc)})
        audit=self.fixture.audits[0].model_copy(update={'actor_key':None,'account_key':'missing','result':'UNKNOWN'})
        issues=service.validate_mapping(self.mapping(sessions=(session,),audits=(audit,)))['issues']
        for code in ['SESSION_ACCOUNT_MISSING','SESSION_INTERVAL_INVALID','AUDIT_ACCOUNT_MISSING','AUDIT_LINEAGE_INCOMPLETE']:self.assertIn(code,issues)
    def test_router_scope_filters_before_count_and_pagination(self):
        scoped={**self.user,'permissions':{self.id:{'can_view':True,'can_view_reports':True}}}
        with patch.object(service,'fixture_for',wraps=service.fixture_for) as fixtures:
            result=service.inventory(scoped,page=1,page_size=1);self.assertEqual(result['total'],1);self.assertEqual(result['items'][0]['router_id'],self.id);fixtures.assert_called_once_with(self.id)
            self.assertEqual(service.inventory(scoped,page=2,page_size=1)['items'],[])
        self.assertEqual(service.inventory({**self.user,'permissions':{}})['total'],0)
    def test_foreign_target_404_and_visible_without_report_permission_403(self):
        for user,id,code in [({**self.user,'permissions':{}},self.id,404),({**self.user,'permissions':{self.id:{'can_view':True}}},self.id,403),(self.user,'foreign',404)]:
            for callback in [lambda:service.inventory(user,router_id=id),lambda:service.detail(user,id)]:
                with self.assertRaises(HTTPException) as error:callback()
                self.assertEqual(error.exception.status_code,code)
    def test_read_only_admin_route_metadata_and_no_activation_path(self):
        from app.api.v1.system import router
        from app.core.security import current_admin
        routes=[r for r in router.routes if r.path.startswith('/system/integration-management')];self.assertEqual(len(routes),2)
        for route in routes:self.assertEqual(route.methods,{'GET'});self.assertIn(current_admin,[d.call for d in route.dependant.dependencies])
        detail=service.detail(self.user,self.id);self.assertFalse(detail['rollback_executable']);self.assertIn('SEPARATE_EXECUTION_AUTHORIZATION',detail['pilot_gates'])
    def test_fixtures_reject_secrets_live_source_or_arbitrary_properties(self):
        for extra in [dict(source='V1'),dict(password='secret'),dict(secret_reference='secretref:v2/owner/key'),dict(endpoint='https://production')]:
            with self.assertRaises(ValidationError):service.MappingSet(**extra)
        response=service.detail(self.user,self.id);self.assertNotIn('secretref:',str(response));self.assertNotIn('password',str(response))
    def test_review_flag_is_not_execution_authority_and_existing_fixtures_are_immutable(self):
        before=deepcopy(ROUTERS);response=service.inventory(self.user)
        reviewed=next(r for r in response['items'] if r['preparation']=='APPROVAL_REQUIRED');self.assertTrue(reviewed['synthetic_review_complete']);self.assertFalse(reviewed['execution_authorized']);self.assertTrue(reviewed['pilot_approval_required']);self.assertEqual(ROUTERS,before)
    def test_corrupt_fixture_is_blocked_and_does_not_echo_secret_or_affect_other_router(self):
        original=service.fixture_for
        def fixture(id):
            if id==self.id:raise ValueError('secretref:v2/private/key')
            return original(id)
        with patch.object(service,'fixture_for',side_effect=fixture):result=service.inventory(self.user)
        self.assertEqual(result['items'][0]['preparation'],'BLOCKED');self.assertNotIn('secretref:',str(result));self.assertEqual(result['items'][-1]['preparation'],'APPROVAL_REQUIRED')
    def test_duplicate_ids_across_router_fixture_bundle_fail_closed(self):
        other,_=service.fixture_for(ROUTERS[-1]['id'])
        copied=other.accounts[0].model_copy(update={'target_key':self.fixture.accounts[0].target_key})
        bundle=service.MappingSet(routers=self.fixture.routers+other.routers,accounts=self.fixture.accounts+(copied,))
        self.assertIn('ACCOUNT_TARGET_COLLISION',service.validate_mapping(bundle)['issues'])
    def test_viewer_and_restricted_admin_are_rejected_by_backend_guard(self):
        from app.core.security import current_admin
        for identity in [dict(is_demo=True,role_code='VIEWER',can_manage_users=False),dict(is_demo=True,role_code='ADMIN',can_manage_users=False)]:
            with self.assertRaises(HTTPException) as error:current_admin(identity)
            self.assertEqual(error.exception.status_code,403)

    def test_expiry_does_not_silently_convert_epoch_or_timestamp_to_calendar_day(self):
        values=self.fixture.accounts[0].model_dump()
        for value in [0,86400,datetime(2026,10,28,tzinfo=timezone.utc),'2026-10-28T00:00:00Z']:
            with self.assertRaises(ValidationError):service.AccountMapping.model_validate({**values,'expiry_mode':'DATE','expires_on':value})
