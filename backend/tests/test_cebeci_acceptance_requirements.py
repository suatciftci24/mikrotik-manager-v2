"""Stage 27 only: canonical criteria, source/TTL/STOP and approval boundaries."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.integrations import cebeci_account_preparation as prep
from app.integrations.cebeci_decision_packet import decision_packet
from app.integrations.cebeci_preparation import profile
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS,SUBSCRIBERS
AT=datetime(2026,10,29,12,tzinfo=timezone.utc)
class AcceptanceRequirementsTests(TestCase):
    def setUp(self):self.user=public_user(bootstrap())
    def claims(self,**changes):
        packet=prep.prepare(self.user,now=AT)['packet_sha256']
        return tuple(prep.PreparationClaim(**{'field':key,'outcome':'PASS','source':'SYNTHETIC_FIXTURE','observed_at':AT,'packet_sha256':packet,**changes}) for key,*_ in prep.FIELDS)
    def test_same_nine_eight_twenty_have_complete_canonical_acceptance_rules(self):
        source=profile(self.user)['access_preparation'];self.assertEqual(len(source['prerequisites']['matrix']),9)
        self.assertEqual(len(source['account_preparation']['groups']),8)
        rows=source['account_preparation']['evidence_fields'];self.assertEqual(len(rows),20)
        self.assertEqual(set(prep.EVIDENCE_RULES),{row['field'] for row in rows})
        for row in rows:
            self.assertEqual(row['validity_seconds'],300);self.assertTrue(row['evidence_required'])
            self.assertEqual({key:row[key] for key in prep.RULE_KEYS},prep.evidence_requirements(row['field']))
            self.assertTrue(all(row[key] for key in prep.RULE_KEYS))
        self.assertTrue(source['decision_packet']['sources_complete'])
    def test_live_account_tls_ipsec_source_firewall_v1_proofs_need_explicit_approval(self):
        for key in ('ACCOUNT_SEPARATE','IPSEC_AUTH','IPSEC_PATH','SOURCE_ACCOUNT','SOURCE_SERVICE','SOURCE_FIREWALL','ROUTER_IDENTITY','TLS_CHAIN','TLS_NAME','TLS_VALIDITY','TLS_PIN','V1_IMPACT'):
            self.assertEqual(prep.evidence_requirements(key)['approval_requirement'],prep.LIVE)
        for key in ('ACCOUNT_AUTH','POLICY_EXACT','ROS6_LAB','TLS_CLIENT','AUDIT','STOP_OWNER','ROLLBACK'):
            self.assertEqual(prep.evidence_requirements(key)['approval_requirement'],prep.OFFLINE)
        self.assertEqual(prep.evidence_requirements('OPERATOR_REVIEW')['approval_requirement'],'SEPARATE_EXPLICIT_USER_APPROVAL_AND_EXECUTION_REVIEW')
    def test_criteria_revision_invalidates_prior_packet_without_authorizing_anything(self):
        claims=self.claims();old=claims[0].packet_sha256
        changed=dict(prep.EVIDENCE_RULES);rule=changed['TLS_CHAIN'];changed['TLS_CHAIN']=(rule[0]+' REVISION',*rule[1:])
        with patch.object(prep,'EVIDENCE_RULES',changed):
            result=prep.prepare(self.user,claims,now=AT)
        self.assertNotEqual(result['packet_sha256'],old)
        self.assertTrue(all(row['reason_code']=='POLICY_PACKET_CHANGED' for row in result['evidence_fields']))
        self.assertEqual(result['decision'],'NO_GO')
    def test_missing_modified_or_wrong_ttl_rules_are_integrity_errors(self):
        base=profile(self.user)['access_preparation']
        for update in ({'acceptance_criteria':None},{'expected_source':'UNREVIEWED_SOURCE'},{'approval_requirement':'NO_APPROVAL_NEEDED'},{'validity_seconds':86400}):
            source=deepcopy(base);source['account_preparation']['evidence_fields'][0].update(update)
            packet=decision_packet(self.user,source)
            self.assertIn('EVIDENCE_ACCEPTANCE_RULES_INVALID',packet['integrity_errors']);self.assertFalse(packet['sources_complete'])
            self.assertEqual(packet['decision'],'NO_GO')
    def test_old_manual_unknown_dates_and_zero_verified_are_preserved(self):
        source=profile(self.user)['access_preparation'];self.assertIsNone(source['manual_review']['observed_at'])
        self.assertTrue(all(row['observed_at'] is None for row in source['manual_review']['findings']))
        self.assertEqual(source['decision_packet']['counts']['verified'],0);self.assertEqual(source['decision_packet']['counts']['unknown_time'],28)
        result=prep.prepare(self.user,self.claims(source='MANUAL_OBSERVATION'),now=AT)
        self.assertTrue(all(row['status']=='UNVERIFIED' for row in result['evidence_fields']))
    def test_stale_future_and_unknown_claims_cannot_satisfy_descriptive_acceptance(self):
        for observed,state in [(None,'UNKNOWN'),(AT-timedelta(minutes=5),'STALE'),(AT+timedelta(seconds=1),'UNKNOWN')]:
            result=prep.prepare(self.user,self.claims(observed_at=observed),now=AT)
            self.assertTrue(all(row['status']==state for row in result['evidence_fields']));self.assertFalse(result['connection_allowed'])
            self.assertEqual(result['decision'],'NO_GO')
    def test_complete_synthetic_criteria_cannot_grant_operator_approval_execution_or_tls_exception(self):
        result=prep.prepare(self.user,self.claims(),now=AT)
        self.assertTrue(result['synthetic_checklist_complete']);self.assertEqual(result['operator_approval'],'NOT_RECORDED')
        self.assertEqual(result['execution_authority'],'DENIED');self.assertFalse(result['connection_allowed'])
        self.assertEqual(result['transport_options'][1]['status'],'BLOCKED_BY_CURRENT_TLS_CONTRACT')
        self.assertEqual(result['current_transport_contract'],'API_SSL');self.assertEqual(result['decision'],'NO_GO')
    def test_rule_requirements_do_not_add_raw_secret_or_approval_input_fields(self):
        claim=self.claims()[0]
        for extra in ('password','psk','private_key','sa','acceptance_criteria','operator_approval'):
            with self.assertRaisesRegex(ValueError,'ACCOUNT_PREPARATION_CONTRACT_REJECTED') as failure:
                prep.prepare(self.user,(claim.model_copy(update={extra:'SECRET_CANARY'}),),now=AT)
            self.assertNotIn('SECRET_CANARY',str(failure.exception))
    def test_admin_existing_get_and_offline_profile_preserve_baselines(self):
        from app.api.v1.system import router
        before=deepcopy((ROUTERS,SUBSCRIBERS))
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):self.assertEqual(profile(self.user),profile(self.user))
        self.assertEqual((ROUTERS,SUBSCRIBERS),before)
        self.assertEqual([(r.path,r.methods) for r in router.routes if 'cebeci' in r.path],[('/system/cebeci-pilot',{'GET'})])
        for change in ({'role_code':'VIEWER'},{'can_manage_users':False}):
            with self.assertRaises(HTTPException):decision_packet({**self.user,**change},{})
