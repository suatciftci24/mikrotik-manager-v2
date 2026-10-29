"""Stage 25 only: account capability and independent synthetic preparation evidence."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.integrations import cebeci_account_preparation as prep
from app.integrations.cebeci_preparation import profile
from app.integrations.cebeci_access import AccessPlan,OfflineEvidence,ReadIntent,dispatch_pilot_read
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS,SUBSCRIBERS
AT=datetime(2026,10,29,12,tzinfo=timezone.utc)
class PilotAccountPreparationTests(TestCase):
    def setUp(self):self.user=public_user(bootstrap())
    def claims(self):
        packet=prep.prepare(self.user,now=AT)['packet_sha256']
        return tuple(prep.PreparationClaim(field=key,outcome='PASS',source='SYNTHETIC_FIXTURE',observed_at=AT,packet_sha256=packet) for key,*_ in prep.FIELDS)
    def evaluate(self,claims=None,**kw):return prep.prepare(self.user,self.claims() if claims is None else claims,now=AT,**kw)
    def field(self,result,key):return next(row for row in result['evidence_fields'] if row['field']==key)
    def test_default_has_eight_groups_twenty_missing_fields_and_no_account_or_connection(self):
        result=self.evaluate(())
        self.assertEqual(len(result['groups']),8);self.assertEqual(len(result['evidence_fields']),20)
        for row in result['evidence_fields']:self.assertEqual(row['status'],'MISSING');self.assertIsNone(row['observed_at'])
        self.assertEqual(result['operator_approval'],'NOT_RECORDED');self.assertEqual(result['execution_authority'],'DENIED')
        for key in ('network_enabled','connection_allowed','account_creation_allowed','polling','automatic_retry','live_verification','manual_observations_promoted'):self.assertFalse(result[key])
        self.assertEqual(result['decision'],'NO_GO')
    def test_minimum_policy_exact_allowlist_forbids_every_extra_and_missing_permission(self):
        self.assertEqual(prep.PilotAccountContract(policies=('api','read')).policies,('read','api'))
        for policy in (*prep.FORBIDDEN_POLICIES,'unknown'):
            with self.assertRaises(ValueError):prep.PilotAccountContract(policies=('read','api',policy))
        for policies in ((),('read',),('api',),('read','api','read')):
            with self.assertRaises(ValueError):prep.PilotAccountContract(policies=policies)
    def test_tls_ipsec_source_and_v1_fields_cannot_satisfy_each_other(self):
        claims=self.claims()
        for key in ('TLS_CHAIN','TLS_NAME','TLS_PIN','IPSEC_AUTH','IPSEC_PATH','SOURCE_ACCOUNT','SOURCE_SERVICE','SOURCE_FIREWALL','V1_IMPACT','ROS6_LAB'):
            result=self.evaluate(tuple(claim for claim in claims if claim.field!=key))
            self.assertEqual(self.field(result,key)['status'],'MISSING');self.assertFalse(result['synthetic_checklist_complete'])
            self.assertEqual(result['decision'],'NO_GO');self.assertIn(key,result['transport_options'][0]['missing_fields'])
        result=self.evaluate(tuple(claim for claim in claims if claim.field!='TLS_CHAIN'))
        self.assertNotIn('TLS_CHAIN',result['transport_options'][1]['required_fields'])
        self.assertEqual(result['transport_options'][1]['status'],'BLOCKED_BY_CURRENT_TLS_CONTRACT')
    def test_even_perfect_synthetic_account_and_approval_review_cannot_authorize_execution(self):
        result=self.evaluate();self.assertTrue(result['synthetic_checklist_complete']);self.assertEqual(result['decision'],'NO_GO')
        self.assertEqual(next(row for row in result['groups'] if row['id']=='OPERATOR_APPROVAL')['status'],'NOT_RECORDED')
        self.assertEqual(result['operator_approval'],'NOT_RECORDED');self.assertFalse(result['account_creation_allowed'])
        for option in result['transport_options']:self.assertFalse(option['approved']);self.assertFalse(option['connection_allowed'])
        with self.assertRaises(ValueError):AccessPlan(transport='API',port=8728)
        with self.assertRaises(HTTPException):dispatch_pilot_read(self.user,AccessPlan(),OfflineEvidence(),ReadIntent(menu='/system/identity',properties=('name',)),object())
    def test_manual_and_offline_pass_never_promoted_to_verified_or_synthetic_pass(self):
        claims=self.claims()
        for source in ('MANUAL_OBSERVATION','OFFLINE_UNVERIFIED'):
            result=self.evaluate(tuple(claim.model_copy(update={'source':source}) for claim in claims))
            self.assertFalse(result['synthetic_checklist_complete'])
            self.assertTrue(all(row['status']=='UNVERIFIED' for row in result['evidence_fields']))
    def test_stale_future_missing_timestamp_and_negative_evidence_fail_closed(self):
        claims=self.claims()
        for update,status in [({'observed_at':AT-timedelta(minutes=5)},'STALE'),({'observed_at':AT+timedelta(seconds=1)},'UNKNOWN'),({'observed_at':None},'UNKNOWN'),({'outcome':'FAILED'},'BLOCKED'),({'outcome':'UNKNOWN'},'UNKNOWN')]:
            result=self.evaluate((claims[0].model_copy(update=update),)+claims[1:])
            self.assertEqual(self.field(result,'ACCOUNT_SEPARATE')['status'],status);self.assertEqual(result['decision'],'NO_GO')
    def test_duplicate_or_wrong_packet_evidence_is_conflict_not_latest_wins(self):
        claims=self.claims()
        for rows in (claims+(claims[0],),(claims[0].model_copy(update={'packet_sha256':'b'*64}),)+claims[1:]):
            self.assertEqual(self.field(self.evaluate(rows),'ACCOUNT_SEPARATE')['status'],'CONFLICT')
    def test_no_credential_live_source_approval_or_provisioner_fields_even_via_model_copy(self):
        claim=self.claims()[0]
        for update in ({'password':'SECRET_CANARY'},{'private_key':'SECRET_CANARY'},{'psk':'SECRET_CANARY'},{'sa':'SECRET_CANARY'},{'source':'LIVE'},{'operator_approval':True},{'candidate_id':'OTHER'},{'observed_at':123}):
            with self.assertRaisesRegex(ValueError,'^ACCOUNT_PREPARATION_CONTRACT_REJECTED$') as failure:self.evaluate((claim.model_copy(update=update),))
            self.assertNotIn('SECRET_CANARY',str(failure.exception))
        for update in ({'policies':('read','api','write')},{'username':'SECRET_CANARY'},{'account_creation_allowed':True}):
            with self.assertRaises(ValueError):self.evaluate((),contract=prep.PilotAccountContract().model_copy(update=update))
    def test_admin_profile_has_no_new_routes_network_or_data_mutation(self):
        from app.api.v1.system import router
        before=deepcopy((ROUTERS,SUBSCRIBERS))
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            result=profile(self.user);self.assertEqual(result,profile(self.user))
        self.assertEqual((ROUTERS,SUBSCRIBERS),before)
        self.assertEqual(result['access_preparation']['account_preparation']['account_status'],'NOT_CREATED_NOT_VERIFIED')
        self.assertEqual([(r.path,r.methods) for r in router.routes if 'cebeci' in r.path],[('/system/cebeci-pilot',{'GET'})])
        for changes in ({'role_code':'VIEWER'},{'can_manage_users':False}):
            with self.assertRaises(HTTPException):prep.prepare({**self.user,**changes},now=AT)
