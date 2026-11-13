"""Read-only observer port and synthetic authenticated evidence; no remote IO."""
from datetime import datetime, timedelta
from hmac import digest, compare_digest
from typing import Protocol
from uuid import UUID
from pydantic import Field, SecretBytes
from app.integrations.aaa_contracts import ReadContract
from app.repositories.aaa_reconciliation import RemoteObservation
from app.simulation.aaa_atomic import canonical_hash


class ObservationChallenge(ReadContract):
    evaluation_id: UUID
    execution_id: UUID
    tenant_id: UUID
    operation_id: UUID
    subscriber_id: str
    router_id: str
    plan_hash: str
    dispatch_fingerprint: str
    owner_revision: int
    fence: int
    requested_at: datetime
    deadline: datetime


class SignedRemoteEvidence(ReadContract):
    fixture_only: bool = True
    challenge_hash: str
    observation: RemoteObservation
    signature: str = Field(repr=False,exclude=True,pattern=r'^[0-9a-f]{64}$')


class RemoteObserver(Protocol):
    """Implementations must bound IO to challenge.deadline; no writes or retry."""
    def observe(self, challenge: ObservationChallenge) -> SignedRemoteEvidence | None: ...


def signature(key, challenge_hash, observation):
    body = canonical_hash([challenge_hash,observation.model_dump(mode='json')]).encode()
    return digest(key.get_secret_value(),body,'sha256').hex()


class SyntheticRemoteObserver:
    """Independent caller-owned observation registry. Never derives outcome from a request."""
    def __init__(self, observations, *, key: SecretBytes, source_identity, source_revision):
        self._observations = tuple(observations)
        if type(key) is not SecretBytes or len(key.get_secret_value()) < 32:
            raise TypeError('SYNTHETIC_OBSERVER_KEY_REQUIRED')
        if any(type(o) is not RemoteObservation for o in self._observations):
            raise TypeError('TYPED_REMOTE_OBSERVATIONS_REQUIRED')
        self._key,self.source_identity,self.source_revision = key,source_identity,source_revision

    def observe(self, challenge):
        matches = [o for o in self._observations if o.execution_id==challenge.execution_id]
        if len(matches) != 1: return None
        observation = matches[0].model_copy(update={'source_identity':self.source_identity,
                                                    'source_revision':self.source_revision})
        challenge_hash = canonical_hash(challenge.model_dump(mode='json'))
        return SignedRemoteEvidence(challenge_hash=challenge_hash,observation=observation,
                                    signature=signature(self._key,challenge_hash,observation))


class RemoteEvidenceVerifier:
    """Pinned synthetic source key/version; signature never confers write authority."""
    def __init__(self, *, key: SecretBytes, source_identity, source_revision):
        if (type(key) is not SecretBytes or len(key.get_secret_value()) < 32
                or not isinstance(source_identity,str) or not source_identity.startswith('fixture-observer-')
                or type(source_revision) is not int or source_revision<1):
            raise TypeError('PINNED_FIXTURE_SOURCE_REQUIRED')
        self._key,self.source_identity,self.source_revision = key,source_identity,source_revision

    def verify(self, envelope, challenge, now):
        try:
            if type(envelope) is not SignedRemoteEvidence or envelope.fixture_only is not True:
                return None
            if (now.utcoffset() is None or challenge.requested_at.utcoffset() is None
                    or challenge.deadline.utcoffset() is None
                    or not challenge.requested_at<=now<challenge.deadline
                    or challenge.deadline-challenge.requested_at>timedelta(seconds=5)):
                return None
            observation = RemoteObservation.model_validate_json(envelope.observation.model_dump_json())
            expected = canonical_hash(challenge.model_dump(mode='json'))
            if (envelope.challenge_hash != expected
                    or (observation.source_identity,observation.source_revision)!=(self.source_identity,self.source_revision)
                    or not compare_digest(envelope.signature,signature(self._key,expected,observation))):
                return None
            fields = ('tenant_id','operation_id','execution_id','subscriber_id','router_id','plan_hash',
                      'dispatch_fingerprint','owner_revision','fence')
            if any(getattr(observation,k)!=getattr(challenge,k) for k in fields):
                return None
            if (observation.observed_at.utcoffset() is None or observation.valid_until.utcoffset() is None
                    or not observation.observed_at<=now<observation.valid_until
                    or now-observation.observed_at>timedelta(seconds=30)
                    or observation.valid_until-observation.observed_at>timedelta(seconds=30)):
                return None
            return observation
        except Exception:
            return None
