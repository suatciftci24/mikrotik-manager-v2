"""Stage 26: derived packet consistency, provenance and unchanged closed boundary."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.integrations.cebeci_preparation import profile
from app.integrations.cebeci_decision_packet import decision_packet,MATRIX_FIELDS
from app.integrations.cebeci_account_preparation import FIELDS,GROUPS
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS,SUBSCRIBERS

class DecisionPacketTests(TestCase):
    def setUp(self):self.user=public_user(bootstrap());self.security=profile(self.user)['access_preparation']
    def packet(self):return decision_packet(self.user,self.security)
    def test_packet_joins_existing_nine_eight_twenty_without_new_evidence_model(self):
        before=deepcopy(self.security);packet=self.packet()
        self.assertTrue(packet['sources_complete']);self.assertEqual(len(packet['matrix_links']),9)
        covered={field for link in packet['matrix_links'] for field in link['field_refs']}
        self.assertEqual(covered,{key for key,*_ in FIELDS});self.assertEqual(len(covered),20)
        self.assertEqual({group for link in packet['matrix_links'] for group in link['group_refs']},{key for key,*_ in GROUPS})
        self.assertEqual(self.security,before)
        for name in ('evidence_fields','groups','matrix','findings','transport_options'):self.assertNotIn(name,packet)
    def test_default_manual_unknown_missing_verified_and_expired_are_distinct(self):
        packet=self.packet();self.assertEqual(packet['counts']['missing'],20);self.assertEqual(packet['counts']['manual'],8)
        self.assertEqual(packet['counts']['verified'],0);self.assertEqual(packet['counts']['expired'],0)
        self.assertEqual(packet['counts']['unknown_time'],28)
        self.assertTrue(all(ref.startswith('manual:') for ref in packet['evidence_buckets']['manual']))
        self.assertIsNone(self.security['manual_review']['observed_at'])
    def test_manual_and_stale_axes_overlap_without_promotion_to_verified(self):
        field=self.security['account_preparation']['evidence_fields'][0]
        field.update(status='STALE',source='MANUAL_OBSERVATION',observed_at='2026-10-29T00:00:00+00:00')
        finding=self.security['manual_review']['findings'][0];finding.update(freshness='STALE',observed_at='2026-10-29T00:00:00+00:00')
        packet=self.packet();ref='field:'+field['field']
        self.assertIn(ref,packet['evidence_buckets']['expired']);self.assertIn(ref,packet['evidence_buckets']['manual'])
        self.assertIn('manual:'+finding['id'],packet['evidence_buckets']['expired'])
        self.assertNotIn(ref,packet['evidence_buckets']['missing']);self.assertEqual(packet['counts']['verified'],0)
    def test_complete_synthetic_sources_never_imply_real_approval_or_authority(self):
        for row in self.security['account_preparation']['evidence_fields']:row.update(status='SYNTHETIC_REVIEW_PASS',source='SYNTHETIC_FIXTURE')
        packet=self.packet();self.assertEqual(packet['counts']['synthetic'],20);self.assertEqual(packet['counts']['verified'],0)
        self.assertEqual(packet['decision'],'NO_GO');self.assertEqual(packet['technical_suitability'],'NOT_VERIFIED')
        self.assertEqual(packet['operator_approval'],'NOT_RECORDED');self.assertEqual(packet['execution_authority'],'DENIED')
        self.assertFalse(packet['network_enabled']);self.assertFalse(packet['account_creation_allowed']);self.assertFalse(packet['connection_allowed'])
        self.assertTrue(packet['operator_questions']);self.assertTrue(packet['safe_next_steps'])
    def test_unsupported_verified_or_manual_pass_state_is_blocked_not_trusted(self):
        row=self.security['account_preparation']['evidence_fields'][0]
        for status,source,code in [('VERIFIED','LIVE','UNSUPPORTED_EVIDENCE_STATE'),('SYNTHETIC_REVIEW_PASS','MANUAL_OBSERVATION','UNTRUSTED_PASS_STATE')]:
            row.update(status=status,source=source);packet=self.packet()
            self.assertFalse(packet['sources_complete']);self.assertIn(code,packet['integrity_errors'])
            self.assertEqual(packet['counts']['verified'],0);self.assertEqual(packet['decision'],'NO_GO')
    def test_missing_duplicate_and_unknown_references_fail_closed_without_echoing_unknown_ids(self):
        row=self.security['account_preparation']['evidence_fields'][0];row['field']='SECRET_CANARY'
        packet=self.packet();self.assertIn('FIELD_REFERENCES_INVALID',packet['integrity_errors']);self.assertNotIn('SECRET_CANARY',str(packet))
        self.security['account_preparation']['groups']*=2
        self.assertIn('GROUP_REFERENCES_INVALID',self.packet()['integrity_errors'])
        packet=decision_packet(self.user,{});self.assertFalse(packet['sources_complete']);self.assertEqual(packet['decision'],'NO_GO')
    def test_tls_ipsec_exception_and_authority_tampering_cannot_open_packet(self):
        self.security['configuration']['transport']='API'
        prep=self.security['account_preparation'];prep['operator_approval']='APPROVED';prep['network_enabled']=True
        prep['transport_options'][1].update(status='APPROVED',approved=True,connection_allowed=True)
        packet=self.packet()
        for code in ('TLS_CONTRACT_INVALID','AUTHORITY_BOUNDARY_INVALID','CLOSED_BOUNDARY_INVALID','TRANSPORT_BOUNDARY_INVALID'):self.assertIn(code,packet['integrity_errors'])
        self.assertEqual(packet['decision'],'NO_GO');self.assertFalse(packet['connection_allowed'])
        self.assertIn('API8728_TLS_EXCEPTION_NOT_GRANTED',packet['hard_blocks'])
    def test_manual_links_use_existing_findings_and_matrix_stop_owner_requirements(self):
        packet=self.packet();known={row['id'] for row in self.security['manual_review']['findings']}
        for link in packet['matrix_links']:
            self.assertTrue(set(link['manual_refs'])<=known)
            self.assertEqual(link['field_refs'],list(MATRIX_FIELDS[link['criterion']]))
            self.assertTrue(next(row for row in self.security['prerequisites']['matrix'] if row['criterion']==link['criterion'])['responsible_role'])
    def test_admin_profile_read_only_no_sockets_no_mutations_no_new_execution_route(self):
        from app.api.v1.system import router
        before=deepcopy((ROUTERS,SUBSCRIBERS))
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            self.assertEqual(profile(self.user),profile(self.user))
        self.assertEqual((ROUTERS,SUBSCRIBERS),before)
        self.assertEqual([(r.path,r.methods) for r in router.routes if 'cebeci' in r.path],[('/system/cebeci-pilot',{'GET'})])
        for change in ({'role_code':'VIEWER'},{'can_manage_users':False}):
            with self.assertRaises(HTTPException):decision_packet({**self.user,**change},self.security)
