"""No sockets/DB/device commands: single-candidate plan and synthetic row projection."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
from app.integrations import cebeci_preparation as service
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS
AT=datetime(2026,10,28,12,tzinfo=timezone.utc)
class CebeciPreparationTests(TestCase):
    def setUp(self):self.user=public_user(bootstrap())
    def snapshot(self,**changes):return service.Snapshot(identity='CEBECI_TOWERS',model='RB3011UiAS',version='6.49.19',observed_at=AT,captured_at=AT,**changes)
    def test_historical_profile_does_not_verify_health_or_grant_device_access(self):
        result=service.profile(self.user);self.assertEqual(result['historical']['management_address'],'10.250.0.19');self.assertEqual(result['historical']['ipsec_center_address'],'10.250.0.1');self.assertIsNone(result['historical']['verified_at']);self.assertEqual(result['connection'],'NOT CONNECTED');self.assertEqual(result['authorization']['binding'],'UNASSIGNED');self.assertFalse(result['execution_authorized']);self.assertEqual(result['approval'],'APPROVAL REQUIRED')
    def test_only_exact_candidate_is_visible_and_existing_admin_grants_are_not_device_grants(self):
        for id in ['other-router','cebeci_towers','10.250.0.19',ROUTERS[0]['id']]:
            with self.assertRaises(HTTPException) as error:service.profile(self.user,id)
            self.assertEqual(error.exception.status_code,404)
        for action in ['DEVICE_READ','EXECUTE','APPROVE']:
            with self.assertRaises(HTTPException) as error:service.authorize(self.user,purpose=action)
            self.assertEqual(error.exception.status_code,403)
    def test_viewer_and_limited_admin_are_denied_before_profile_data(self):
        for identity in [{**self.user,'role_code':'VIEWER'},{**self.user,'can_manage_users':False}]:
            with self.assertRaises(HTTPException) as error:service.profile(identity)
            self.assertEqual(error.exception.status_code,403)
    def test_eight_routeros6_menus_have_explicit_bounded_read_properties(self):
        result=service.profile(self.user);self.assertEqual(len(result['read_scope']),8)
        menus={r['menu'] for r in result['read_scope']};self.assertIn('/ip/ipsec/active-peers',menus);self.assertIn('/ip/ipsec/installed-sa',menus)
        self.assertNotIn('routing-table',service.READ_FIELDS['/ip/route']);self.assertTrue(all(r['compatibility']=='ROS6_LAB_VERIFICATION_REQUIRED' for r in result['read_scope']))
    def test_sensitive_field_broad_read_and_writing_descriptors_are_rejected(self):
        for menu,fields in [('/ppp/secret',()),('/ppp/secret',('password',)),('/ip/ipsec/installed-sa',('enc-key',)),('/ip/ipsec/installed-sa',('auth-key',)),('/system/reboot',('name',)),('/ppp/secret/set',('disabled',)),('/system/script/run',('name',)),('/ip/route',('routing-table',))]:
            with self.assertRaises(ValueError):service.validate_read_descriptor(menu,fields)
        self.assertEqual(service.validate_read_descriptor('/ppp/secret',('name','profile')),('name','profile'))
    def test_receiver_drops_additional_secret_and_unrequested_fields(self):
        canary='never-serialize-test-key';rows={'state':'mature','enc-key':canary,'auth-key':canary,'secretref':'secretref:v2/private/key'}
        projected=service.project_fixture_row('/ip/ipsec/installed-sa',rows);self.assertEqual(projected,{'state':'mature'});self.assertNotIn(canary,str(projected))
        self.assertEqual(service.project_fixture_row('/ppp/secret',{'name':'synthetic-user','password':canary}),{'name':'synthetic-user'})
        self.assertEqual(service.project_fixture_row('/ppp/secret',{'name':{'token':canary}}),{})
    def test_wrong_identity_model_and_version_are_stop_not_silent_remapping(self):
        for key,value,code in [('identity','WRONG_ROUTER','WRONG_ROUTER_IDENTITY'),('model','RB5009','MODEL_MISMATCH'),('version','7.16.2','VERSION_MISMATCH')]:
            result=service.compare(self.snapshot().model_copy(update={key:value}),AT);self.assertEqual(result['result'],'STOP');self.assertIn(code,result['stop_codes']);self.assertFalse(result['execution_authorized'])
    def test_stale_unknown_and_clock_skew_never_become_wan_or_ipsec_down(self):
        for snapshot,code in [(self.snapshot().model_copy(update={'observed_at':None}),'OBSERVATION_TIME_UNKNOWN'),(self.snapshot().model_copy(update={'observed_at':AT-timedelta(days=1)}),'STALE_SYNTHETIC_OBSERVATION'),(self.snapshot().model_copy(update={'captured_at':AT+timedelta(seconds=1)}),'CLOCK_SKEW_UNKNOWN')]:
            result=service.compare(snapshot,AT);self.assertIn(code,result['unknown']+result['warnings']);self.assertEqual(result['wan_status'],'UNKNOWN');self.assertEqual(result['ipsec_status'],'UNKNOWN')
    def test_different_timestamps_are_not_collapsed_to_capture_time(self):
        result=service.compare(self.snapshot().model_copy(update={'observed_at':AT-timedelta(seconds=1)}),AT);self.assertIn('DIFFERENT_SOURCE_CAPTURE_TIMES',result['warnings'])
    def test_missing_and_empty_ipsec_sources_are_distinct_unknowns(self):
        missing=service.compare(self.snapshot(),AT);empty=service.compare(self.snapshot(rows={'/ip/ipsec/active-peers':[]}),AT)
        self.assertIn('PATH_UNMEASURED:/ip/ipsec/active-peers',missing['unknown']);self.assertIn('EMPTY_SOURCE:/ip/ipsec/active-peers',empty['unknown'])
    def test_backend_authority_and_expire_are_not_inferred_from_local_secret_presence(self):
        result=service.compare(self.snapshot(rows={'/ppp/secret':[{'name':'synthetic-user','profile':'fixture-basic'}]}),AT);self.assertEqual(result['pppoe_backend'],'UNKNOWN');self.assertIn('disabled',result['missing_fields']['/ppp/secret']);self.assertNotIn('expires_on',service.READ_FIELDS['/ppp/secret'])
    def test_duplicate_account_identity_is_stop_and_payload_values_not_echoed(self):
        result=service.compare(self.snapshot(rows={'/ppp/secret':[{'name':'synthetic-user'},{'name':'synthetic-user'}]}),AT);self.assertIn('ACCOUNT_IDENTITY_COLLISION',result['stop_codes']);self.assertNotIn('synthetic-user',str(result))
    def test_only_synthetic_snapshots_and_aware_clocks_are_accepted(self):
        with self.assertRaises(ValidationError):service.compare(self.snapshot().model_copy(update={'source':'LIVE'}),AT)
        with self.assertRaises(ValueError):service.compare(self.snapshot(),datetime(2026,1,1))
        with self.assertRaises(ValidationError):service.Snapshot(observed_at=datetime(2026,1,1))
    def test_minimum_policy_is_proposal_not_default_read_group_or_tls_assurance(self):
        result=service.profile(self.user);self.assertEqual(result['security']['proposed_policies'],['read','api']);self.assertIn('sensitive',result['security']['forbidden_policies']);self.assertEqual(result['security']['plain_api'],'BLOCKED');self.assertEqual(result['security']['tls'],'UNKNOWN_REQUIRES_VERIFIED_API_SSL');self.assertFalse(result['automatic_retry']);self.assertFalse(result['polling'])
    def test_stop_matrix_includes_writes_permissions_v1_impact_and_no_rollback_execution(self):
        result=service.profile(self.user);self.assertTrue({'UNEXPECTED_WRITE_ATTEMPT','V1_IMPACT','PERMISSION_MISMATCH','ACCESS_ERROR','DATA_INCONSISTENCY'}.issubset(result['stop_conditions']));self.assertFalse(result['rollback_executable'])
    def test_profile_is_deterministic_and_does_not_change_inventory_or_open_network(self):
        before=deepcopy(ROUTERS)
        with patch('socket.create_connection',side_effect=AssertionError('network forbidden')):self.assertEqual(service.profile(self.user),service.profile(self.user))
        self.assertEqual(ROUTERS,before);self.assertNotIn('CEBECI_TOWERS',[r['id'] for r in ROUTERS])
    def test_endpoint_is_admin_get_only(self):
        from app.api.v1.system import router
        from app.core.security import current_admin
        route=next(r for r in router.routes if r.path=='/system/cebeci-pilot');self.assertEqual(route.methods,{'GET'});self.assertIn(current_admin,[d.call for d in route.dependant.dependencies])

    def test_header_cannot_hide_wrong_identity_model_or_version_in_rows(self):
        for menu,row,code in [('/system/identity',{'name':'wrong-router'},'WRONG_ROUTER_IDENTITY'),('/system/resource',{'board-name':'RB5009'},'MODEL_MISMATCH'),('/system/resource',{'version':'7.1'},'VERSION_MISMATCH')]:
            result=service.compare(self.snapshot(rows={menu:[row]}),AT);self.assertEqual(result['result'],'STOP');self.assertIn(code,result['stop_codes'])
    def test_duplicate_source_account_and_session_ids_are_separate_collisions(self):
        result=service.compare(self.snapshot(rows={'/ppp/secret':[{'.id':'fixture-a','name':'fixture-one'},{'.id':'fixture-a','name':'fixture-two'}],'/ppp/active':[{'.id':'fixture-session','name':'fixture-one'},{'.id':'fixture-session','name':'fixture-one'}]}),AT)
        self.assertIn('ACCOUNT_SOURCE_ID_COLLISION',result['stop_codes']);self.assertIn('SESSION_IDENTITY_COLLISION',result['stop_codes'])
    def test_routeros6_string_booleans_are_understood_but_bad_types_stop_without_echo(self):
        row={'.id':'fixture-row','name':'synthetic-user','service':'pppoe','profile':'fixture-profile','disabled':'false'}
        self.assertEqual(service.compare(self.snapshot(rows={'/ppp/secret':[row]}),AT)['stop_codes'],[])
        result=service.compare(self.snapshot(rows={'/ppp/secret':[{**row,'disabled':{'token':'private'}}]}),AT)
        self.assertIn('DATA_INCONSISTENCY',result['stop_codes']);self.assertNotIn('private',str(result))
        result=service.compare(self.snapshot(rows={'/ppp/secret':[{**row,'password':'private'}]}),AT)
        self.assertIn('SENSITIVE_FIELD_RETURNED',result['stop_codes']);self.assertNotIn('private',str(result))
