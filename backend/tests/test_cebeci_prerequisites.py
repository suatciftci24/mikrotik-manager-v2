"""Offline-only Stage 23 matrix and decision separation."""
from datetime import timedelta
from unittest.mock import patch
from app.integrations import cebeci_prerequisites as pre
from tests import test_cebeci_access as fixtures
AT=fixtures.AT

# Reuse only fixture factories, not inherited Stage22 tests.
from unittest import TestCase
from fastapi import HTTPException
class PrerequisiteTests(TestCase):
    def setUp(self):
        fixture=fixtures.CebeciAccessSecurityTests();fixture.setUp()
        self.user=fixture.user;self.plan=fixture.plan();self.evidence=fixture.evidence();self.fixture=fixture
    def receipts(self):
        digest=pre.assess(self.user,self.plan,self.evidence,now=AT)['packet_digest']
        return tuple(pre.EvidenceReceipt(criterion=key,outcome='PASS',source='SYNTHETIC_FIXTURE',reviewer_role=owner,
            artifact_sha256='a'*64,policy_packet_sha256=digest,reviewed_at=AT,expires_at=AT+timedelta(seconds=ttl))
            for key,_,_,ttl,owner,*_ in pre.MATRIX)
    def run_review(self,receipts=None,**kw):return pre.review(self.user,self.receipts() if receipts is None else receipts,plan=self.plan,evidence=kw.pop('evidence',self.evidence),now=kw.pop('now',AT),**kw)
    def row(self,result,key):return next(row for row in result['matrix'] if row['criterion']==key)
    def test_missing_matrix_explains_all_nine_owners_methods_validity_and_stop(self):
        result=pre.review(self.user,now=AT)
        self.assertEqual(len(result['matrix']),9);self.assertEqual(result['missing_prerequisites'],list(pre.KEYS))
        for row in result['matrix']:
            for field in ('evidence_type','verification_method','responsible_role','stop_condition','reason_code'):self.assertTrue(row[field])
            self.assertEqual(row['status'],'MISSING');self.assertIsNone(row['expires_at'])
        self.assertEqual(result['decision'],'NO_GO')
    def test_complete_offline_packet_never_grants_approval_or_execution(self):
        result=self.run_review();self.assertEqual(result['technical_suitability'],'OFFLINE_REVIEW_READY')
        self.assertEqual(result['decision'],'NO_GO');self.assertEqual(result['operator_approval'],'NOT_RECORDED')
        self.assertEqual(result['execution_authority'],'DENIED');self.assertFalse(result['connection_allowed']);self.assertFalse(result['automatic_go'])
    def test_identity_certificate_privilege_and_v1_contradictions_bind_security_engine(self):
        for change,key in [({'observed_identity':'WRONG'},'IDENTITY'),({'hostname_verified':False},'CERTIFICATE'),({'policies':('read','api','write')},'PRIVILEGE'),({'v1_impact_detected':True},'ISOLATION')]:
            evidence=self.fixture.evidence(**change)
            digest=pre.assess(self.user,self.plan,evidence,now=AT)['packet_digest']
            receipts=tuple(row.model_copy(update={'policy_packet_sha256':digest}) for row in self.receipts())
            result=self.run_review(receipts,evidence=evidence)
            self.assertEqual(self.row(result,key)['reason_code'],'SECURITY_GATE_NOT_PASS');self.assertEqual(result['decision'],'NO_GO')
    def test_duplicate_missing_changed_policy_failed_and_unknown_are_explained(self):
        rows=self.receipts()
        for receipts,code in [(rows[1:],'EVIDENCE_MISSING'),(rows+(rows[0],),'DUPLICATE_EVIDENCE'),
            ((rows[0].model_copy(update={'policy_packet_sha256':'b'*64}),)+rows[1:],'POLICY_PACKET_CHANGED'),
            ((rows[0].model_copy(update={'outcome':'FAILED'}),)+rows[1:],'REVIEW_FAILED'),
            ((rows[0].model_copy(update={'outcome':'UNKNOWN'}),)+rows[1:],'REVIEW_UNKNOWN'),
            ((rows[0].model_copy(update={'outcome':'CONFLICT'}),)+rows[1:],'REVIEW_CONFLICT')]:
            result=self.run_review(receipts);self.assertEqual(self.row(result,'IDENTITY')['reason_code'],code);self.assertEqual(result['decision'],'NO_GO')
    def test_expired_future_excessive_ttl_and_wrong_reviewer_fail_closed(self):
        rows=self.receipts()
        for update,code in [({'reviewed_at':AT-timedelta(minutes=10),'expires_at':AT-timedelta(minutes=6)},'EVIDENCE_EXPIRED'),
            ({'reviewed_at':AT+timedelta(seconds=1)},'INVALID_VALIDITY_WINDOW'),
            ({'expires_at':AT+timedelta(days=10)},'INVALID_VALIDITY_WINDOW'),
            ({'reviewer_role':'AUDIT_OWNER'},'REVIEWER_ROLE_MISMATCH')]:
            result=self.run_review((rows[0].model_copy(update=update),)+rows[1:]);self.assertEqual(self.row(result,'IDENTITY')['reason_code'],code)
        self.assertEqual(self.row(self.run_review(now=AT+timedelta(seconds=300)),'IDENTITY')['status'],'STALE')
    def test_forbidden_material_approval_fields_live_source_and_model_copy_rejected(self):
        row=self.receipts()[0]
        for update in ({'password':'secret-canary'},{'operator_approval':True},{'source':'LIVE'},{'criterion':'OTHER_ROUTER'},{'reviewed_at':123}):
            with self.assertRaisesRegex(ValueError,'EVIDENCE_CONTRACT_REJECTED'):self.run_review((row.model_copy(update=update),))
    def test_admin_only_deterministic_and_no_io(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            self.assertEqual(pre.review(self.user,now=AT),pre.review(self.user,now=AT))
        with self.assertRaises(HTTPException):pre.review({**self.user,'role_code':'VIEWER'},now=AT)
