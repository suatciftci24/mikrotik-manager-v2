"""Fixture-only observer key rotation. No remote IO or production key store."""
from dataclasses import dataclass
from pydantic import SecretBytes
from app.integrations.aaa_remote_observer import RemoteEvidenceVerifier


@dataclass(frozen=True)
class FixtureObserverKey:
    key_id: str
    key: SecretBytes
    source_identity: str
    source_revision: int
    revoked: bool = False


class FixtureObserverKeyring:
    def __init__(self, keys):
        self._keys = {}
        for item in keys:
            if (type(item) is not FixtureObserverKey
                    or not item.key_id or item.key_id in self._keys
                    or type(item.key) is not SecretBytes
                    or len(item.key.get_secret_value()) < 32):
                raise ValueError("INVALID_FIXTURE_KEYRING")
            self._keys[item.key_id] = item

    def verify(self, key_id, evidence, challenge, now):
        item = self._keys.get(key_id)
        if item is None or item.revoked:
            return None
        verifier = RemoteEvidenceVerifier(
            key=item.key,
            source_identity=item.source_identity,
            source_revision=item.source_revision,
        )
        return verifier.verify(evidence, challenge, now)
