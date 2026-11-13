from datetime import datetime, timedelta, timezone
import secrets
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from pydantic import SecretBytes
from app.integrations.aaa_remote_observer import (ObservationChallenge, SyntheticRemoteObserver,
    RemoteEvidenceVerifier)
from app.repositories.aaa_reconciliation import RemoteObservation


class RemoteObserverAcceptance(TestCase):
    def setUp(self):
        for name in ('socket.socket','socket.create_connection','psycopg.connect'):
            self.enterContext(patch(name,side_effect=AssertionError('NETWORK_FORBIDDEN')))
        self.now = datetime.now(timezone.utc)
        self.challenge = ObservationChallenge(evaluation_id=uuid4(),execution_id=uuid4(),tenant_id=uuid4(),
            operation_id=uuid4(),subscriber_id='demo-managed-sub-observer',router_id='demo-managed-router-observer',
            plan_hash='a'*64,dispatch_fingerprint='b'*64,owner_revision=3,fence=4,
            requested_at=self.now,deadline=self.now+timedelta(seconds=5))
        self.observation = RemoteObservation(**self.challenge.model_dump(exclude={
            'evaluation_id','requested_at','deadline'}),sequence=1,observed_at=self.now,
            valid_until=self.now+timedelta(seconds=20),outcome='APPLIED')
        self.key = SecretBytes(secrets.token_bytes(32))
        self.options = dict(key=self.key,source_identity='fixture-observer-radius3',source_revision=1)
        self.verifier = RemoteEvidenceVerifier(**self.options)

    def signed(self, observation=None, **options):
        return SyntheticRemoteObserver([observation or self.observation],**{**self.options,**options}).observe(self.challenge)

    def test_authentic_evidence_and_no_key_signature_export(self):
        envelope = self.signed()
        self.assertEqual(self.verifier.verify(envelope,self.challenge,self.now).outcome,'APPLIED')
        public = repr(envelope)+envelope.model_dump_json()+repr(self.verifier)
        self.assertNotIn(envelope.signature,public)
        self.assertNotIn(self.key.get_secret_value().hex(),public)
        self.assertIsNone(self.verifier.verify(envelope.model_copy(update={'signature':'0'*64}),self.challenge,self.now))
        forged = envelope.model_copy(update={'observation':envelope.observation.model_copy(update={'outcome':'NOT_APPLIED'})})
        self.assertIsNone(self.verifier.verify(forged,self.challenge,self.now))

    def test_challenge_replay_untrusted_source_and_key_reject(self):
        for options in ({'source_identity':'fixture-observer-other'},{'source_revision':2},
                        {'key':SecretBytes(secrets.token_bytes(32))}):
            self.assertIsNone(self.verifier.verify(self.signed(**options),self.challenge,self.now))
        replay = self.challenge.model_copy(update={'evaluation_id':uuid4()})
        self.assertIsNone(self.verifier.verify(self.signed(),replay,self.now))
        self.assertIsNone(self.verifier.verify(None,self.challenge,self.now))

    def test_signed_scope_fence_and_dispatch_mismatch_reject(self):
        for change in ({'tenant_id':uuid4()},{'router_id':'demo-managed-router-other'},
                       {'subscriber_id':'demo-managed-sub-other'},{'operation_id':uuid4()},
                       {'dispatch_fingerprint':'c'*64},{'plan_hash':'d'*64},
                       {'owner_revision':4},{'fence':5}):
            self.assertIsNone(self.verifier.verify(self.signed(self.observation.model_copy(update=change)),self.challenge,self.now))

    def test_old_future_expired_and_late_evidence_reject(self):
        for change in ({'observed_at':self.now-timedelta(seconds=31)},
                       {'observed_at':self.now+timedelta(seconds=1)}, {'valid_until':self.now},
                       {'valid_until':self.now+timedelta(seconds=31)}):
            self.assertIsNone(self.verifier.verify(self.signed(self.observation.model_copy(update=change)),self.challenge,self.now))
        self.assertIsNone(self.verifier.verify(self.signed(),self.challenge,self.challenge.deadline))

    def test_legacy_projection_compatibility_and_sparse_serialization(self):
        old = self.observation.model_dump(mode='json')
        self.assertNotIn('source_identity',old)
        self.assertNotIn('source_revision',old)
        self.assertEqual(self.observation,RemoteObservation.model_validate_json(self.observation.model_dump_json()))
        self.assertEqual(self.observation.model_dump(exclude_none=True),self.observation.model_dump())
