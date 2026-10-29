"""Stage 24: operator report mapping only, never live security approval."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.integrations import cebeci_manual as manual
from app.integrations.cebeci_preparation import profile
from app.integrations.cebeci_access import AccessPlan,dispatch_pilot_read,OfflineEvidence,ReadIntent
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS,SUBSCRIBERS
AT=datetime(2026,10,29,12,tzinfo=timezone.utc)

class ManualFindingsTests(TestCase):
    def setUp(self):self.user=public_user(bootstrap())
    def report(self,**changes):return manual.manual_review(self.user,snapshot=manual.ManualIdentityRecord(**changes),now=AT)
    def row(self,result,key):return next(row for row in result['matrix'] if row['criterion']==key)
    def test_unknown_observation_time_is_not_import_or_current_time(self):
        result=self.report();self.assertIsNone(result['observed_at']);self.assertEqual(result['freshness'],'UNKNOWN')
        for finding in result['findings']:
            self.assertIsNone(finding['observed_at']);self.assertEqual(finding['source'],'OPERATOR_REPORTED_MANUAL')
            self.assertEqual(finding['verification_type'],'MANUAL_OBSERVATION');self.assertFalse(finding['independently_verified'])
    def test_identity_report_matches_but_never_verifies_current_identity_or_enables_access(self):
        result=self.report();self.assertTrue(result['identity_match_reported']);self.assertFalse(result['live_identity_verified'])
        self.assertEqual(self.row(result,'IDENTITY')['manual_status'],'MATCH_REPORTED')
        self.assertEqual(result['decision'],'NO_GO');self.assertEqual(result['execution_authority'],'DENIED')
        self.assertEqual(result['operator_approval'],'NOT_RECORDED');self.assertFalse(result['connection_allowed'])
    def test_identity_model_version_mismatch_stops_without_remapping(self):
        for changes in ({'identity':'OTHER_ROUTER'},{'model':'RB5009'},{'version':'7.16.2'}):
            result=self.report(**changes);self.assertFalse(result['identity_match_reported'])
            self.assertEqual(self.row(result,'IDENTITY')['manual_status'],'CONFLICT')
            self.assertIn('MANUAL_IDENTITY_MODEL_VERSION_CONFLICT',result['critical_risks']);self.assertEqual(result['decision'],'NO_GO')
    def test_all_nine_criteria_map_to_manual_or_missing_evidence_not_receipts(self):
        result=self.report();self.assertEqual(len(result['matrix']),9)
        self.assertEqual(set(result['remaining_evidence']),{'IDENTITY','ADDRESS','ISOLATION','CERTIFICATE','PRIVILEGE','READ_SCOPE','SECRET_PROTECTION','AUDIT','STOP'})
        ids={row['id'] for row in result['findings']}
        for row in result['matrix']:
            self.assertEqual(row['status'],'MISSING');self.assertFalse(row['independently_verified'])
            self.assertTrue(set(row['observation_ids'])<=ids);self.assertTrue(row['evidence_type']);self.assertTrue(row['stop_condition'])
        self.assertEqual(self.row(result,'CERTIFICATE')['manual_status'],'BLOCKED_REPORTED')
        self.assertEqual(self.row(result,'PRIVILEGE')['manual_status'],'UNSUITABLE_REPORTED')
        self.assertEqual(self.row(result,'ISOLATION')['manual_status'],'NOT_VERIFIED')
    def test_findings_keep_resources_v1_source_policy_and_partial_firewall_in_context(self):
        findings={row['id']:row['summary'] for row in self.report()['findings']}
        for text in ('%19','956 MiB','81.6 MiB'):self.assertIn(text,findings['RESOURCES'])
        self.assertIn('8728',findings['API']);self.assertIn('10.250.0.1/32',findings['API']);self.assertIn('V2 yetkisi',findings['API'])
        self.assertIn('ph2-count=1',findings['IPSEC_POLICY']);self.assertIn('V2 uçtan uca yol doğrulanmadı',findings['IPSEC_POLICY'])
        self.assertIn('genel firewall güvencesi çıkarılamaz',findings['INPUT_FIREWALL'])
        self.assertIn('write,test',findings['V1_ACCOUNT']);self.assertIn('kaynak sınırı boş',findings['BROAD_ACCOUNTS'])
    def test_stale_future_fresh_reports_are_still_unverified_and_no_go(self):
        for at,status in [(AT-timedelta(minutes=5),'STALE'),(AT+timedelta(seconds=1),'UNKNOWN'),(AT,'WITHIN_REVIEW_WINDOW_NOT_VERIFIED')]:
            result=self.report(observed_at=at);self.assertEqual(result['freshness'],status);self.assertEqual(result['decision'],'NO_GO')
            self.assertFalse(result['live_identity_verified']);self.assertEqual(result['technical_suitability'],'NOT_VERIFIED')
        for at in (datetime(2026,10,29),True,123):
            with self.assertRaises(ValueError):self.report(observed_at=at)
    def test_no_secret_raw_data_or_live_source_intake_even_model_copy(self):
        snapshot=manual.ManualIdentityRecord()
        for changes in ({'password':'SECRET_CANARY'},{'psk':'SECRET_CANARY'},{'sa':'SECRET_CANARY'},{'raw_output':'SECRET_CANARY'},{'source':'LIVE'},{'candidate_id':'OTHER'}):
            with self.assertRaisesRegex(ValueError,'^MANUAL_REPORT_CONTRACT_REJECTED$') as failure:
                manual.manual_review(self.user,snapshot=snapshot.model_copy(update=changes),now=AT)
            self.assertNotIn('SECRET_CANARY',str(failure.exception))
    def test_options_are_comparisons_and_do_not_relax_tls_only_contract(self):
        result=self.report();self.assertEqual([row['id'] for row in result['access_options']],['A','B'])
        for option in result['access_options']:
            self.assertFalse(option['approved']);self.assertFalse(option['connection_allowed'])
            for key in ('encryption','authentication','source_isolation','ros6_limits','v1_impact','operational_risk'):self.assertTrue(option[key])
        self.assertEqual(result['access_options'][1]['status'],'BLOCKED_BY_CURRENT_CONTRACT')
        with self.assertRaises(ValueError):AccessPlan(transport='API',port=8728)
        with self.assertRaises(HTTPException):dispatch_pilot_read(self.user,AccessPlan(),OfflineEvidence(),ReadIntent(menu='/system/identity',properties=('name',)),object())
        self.assertEqual(result['account_plan']['policies'],['read','api']);self.assertTrue(result['account_plan']['existing_accounts_unchanged'])
    def test_admin_profile_integrates_without_network_or_data_mutation(self):
        before=deepcopy((ROUTERS,SUBSCRIBERS))
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            first=profile(self.user);self.assertEqual(first,profile(self.user));self.assertIn('manual_review',first['access_preparation'])
        self.assertEqual((ROUTERS,SUBSCRIBERS),before)
        for changes in ({'role_code':'VIEWER'},{'can_manage_users':False}):
            with self.assertRaises(HTTPException):manual.manual_review({**self.user,**changes},now=AT)
        self.assertEqual(first['access_preparation']['configuration']['transport'],'API_SSL')
        self.assertIsNone(first['access_preparation']['configuration']['reviewed_source_cidr'])
