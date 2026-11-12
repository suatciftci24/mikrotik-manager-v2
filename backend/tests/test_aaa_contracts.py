"""Pure synthetic contract acceptance. No database, socket, secret resolver or writes."""
from datetime import date, datetime, timezone
from unittest import TestCase
from uuid import UUID

from pydantic import ValidationError
from app.integrations.aaa_contracts import (
    AccountReference, AaaIdentity, NasReference, ProfileReference, SubscriptionTerms,
    AaaSnapshot, PreviewScope, PreviewProof, collision_key, inspect_aaa_snapshot,
    snapshot_fingerprint, validate_preview_proof, compare_preview_proofs,
)


class AaaReadContracts(TestCase):
    def snapshot(self, **changes):
        data = dict(reference=AccountReference(store='LEGACY_DEMO', account_id='demo-sub-contract', revision=0),
                    authority='LOCAL', access_type='PPPOE', identity=AaaIdentity(username_raw='User@realm'),
                    nas=NasReference(router_id='demo-router-contract'),
                    profile=ProfileReference(plan_name='Synthetic Plan'),
                    terms=SubscriptionTerms(expires_on=date(2026, 12, 23), account_status='PAUSED'))
        data.update(changes)
        return AaaSnapshot(**data)

    def scope(self, **changes):
        return PreviewScope(**dict(dict(actor_id='synthetic-actor', store='LEGACY_DEMO',
                                        readable_router_ids=('demo-router-contract',)), **changes))

    def proof(self, snapshot, **changes):
        data = dict(request_id=UUID('00000000-0000-4000-8000-000000000001'), actor_id='synthetic-actor',
                    store=snapshot.reference.store, account_id=snapshot.reference.account_id,
                    expected_revision=snapshot.reference.revision, snapshot_sha256=snapshot_fingerprint(snapshot))
        data.update(changes)
        return PreviewProof(**data)

    def test_source_type_and_unknown_are_independent_without_defaults(self):
        for authority in ('LOCAL', 'RADIUS', 'UNKNOWN'):
            for access in ('PPPOE', 'HOTSPOT', 'UNKNOWN'):
                snapshot = self.snapshot(authority=authority, access_type=access)
                result = inspect_aaa_snapshot(snapshot, self.scope())
                self.assertEqual(snapshot.authority, authority)
                self.assertEqual(snapshot.access_type, access)
                self.assertFalse(result['external_writes'])
                self.assertEqual('NOT_A_LOCAL_TRANSITION_CANDIDATE' in result['findings'], authority != 'LOCAL')
                for key in ('nas_mapping', 'profile_mapping', 'subscription_mapping', 'live_identity',
                            'credential_reference', 'aaa_write_authorization'):
                    self.assertEqual(result[key], 'UNVERIFIED')

    def test_missing_refs_do_not_become_a_second_subscription_nas_or_profile(self):
        snapshot = self.snapshot(access_type='UNKNOWN', identity=AaaIdentity(), profile=ProfileReference(),
                                 terms=SubscriptionTerms())
        result = inspect_aaa_snapshot(snapshot, self.scope())
        self.assertIsNone(snapshot.reference.subscription_id)
        self.assertIsNone(snapshot.identity.realm)
        self.assertIsNone(snapshot.nas.nas_id)
        self.assertIsNone(snapshot.profile.aaa_profile_id)
        self.assertTrue({'ACCESS_TYPE_UNKNOWN', 'SUBSCRIPTION_ID_UNKNOWN', 'NAMESPACE_POLICY_UNRESOLVED',
                         'EXPIRATION_MAPPING_UNRESOLVED'} <= set(result['findings']))

    def test_normalization_requires_explicit_exact_policy_and_never_parses_realm(self):
        identity = AaaIdentity(username_raw='User@realm')
        self.assertIsNone(identity.realm)
        self.assertIsNone(identity.username_canonical)
        for changes in (dict(username_canonical='user@realm'),
                        dict(normalization='EXACT', username_canonical='user@realm')):
            with self.assertRaises(ValidationError):
                AaaIdentity(username_raw='User@realm', **changes)
        exact = AaaIdentity(username_raw='User@realm', username_canonical='User@realm', normalization='EXACT')
        self.assertEqual(exact.username_canonical, exact.username_raw)

    def test_namespace_key_requires_tenant_explicit_policy_realm_or_real_nas_ref(self):
        snapshot = self.snapshot()
        self.assertIsNone(collision_key(snapshot))
        ref = AccountReference(store='LEGACY_DEMO', account_id='demo-sub-contract', revision=0, tenant_id='test-tenant')
        identity = AaaIdentity(username_raw='User', username_canonical='User', realm='test-realm', normalization='EXACT')
        exact = self.snapshot(reference=ref, identity=identity, uniqueness_policy='TENANT_REALM_EXACT')
        self.assertEqual(collision_key(exact), ('TENANT_REALM_EXACT', 'test-tenant', 'test-realm', 'User'))
        nas_policy = self.snapshot(reference=ref, identity=identity, uniqueness_policy='TENANT_NAS_EXACT')
        self.assertIsNone(collision_key(nas_policy))  # Router ID cannot stand in for NAS ID.
        nas = NasReference(router_id='demo-router-contract', nas_id=UUID('00000000-0000-4000-8000-000000000002'))
        self.assertIsNotNone(collision_key(self.snapshot(reference=ref, identity=identity, nas=nas,
                                                       uniqueness_policy='TENANT_NAS_EXACT')))

    def test_scope_denies_wrong_store_router_and_nonadmin_workspace_before_results(self):
        for scope in (self.scope(readable_router_ids=()), self.scope(store='PERSISTENT_WORKSPACE', workspace_admin=True)):
            with self.assertRaises(PermissionError):
                inspect_aaa_snapshot(self.snapshot(), scope)
        with self.assertRaises(PermissionError):
            inspect_aaa_snapshot(self.snapshot(), self.scope(tenant_id='other-tenant'))
        persistent = self.snapshot(reference=AccountReference(store='PERSISTENT_WORKSPACE',
                                  account_id='demo-managed-sub-contract', revision=1),
                                  nas=NasReference(router_id='demo-managed-router-contract'))
        with self.assertRaises(PermissionError):
            inspect_aaa_snapshot(persistent, self.scope(store='PERSISTENT_WORKSPACE'))
        self.assertFalse(inspect_aaa_snapshot(persistent, self.scope(store='PERSISTENT_WORKSPACE',
                                                                   workspace_admin=True))['external_writes'])
        with self.assertRaises(ValidationError):
            self.snapshot(nas=NasReference(router_id='registered-live'))

    def test_hidden_peers_are_denied_and_exact_visible_conflicts_remain_risks(self):
        ref = AccountReference(store='LEGACY_DEMO', account_id='demo-sub-contract', revision=0, tenant_id='test-tenant')
        identity = AaaIdentity(username_raw='User', username_canonical='User', realm='test-realm', normalization='EXACT')
        snapshot = self.snapshot(reference=ref, identity=identity, uniqueness_policy='TENANT_REALM_EXACT')
        peer = self.snapshot(reference=AccountReference(store='LEGACY_DEMO', account_id='demo-sub-other',
                             revision=1, tenant_id='test-tenant'), identity=identity,
                             uniqueness_policy='TENANT_REALM_EXACT', authority='RADIUS')
        scope = self.scope(tenant_id='test-tenant')
        result = inspect_aaa_snapshot(snapshot, scope, (peer,))
        self.assertIn('VISIBLE_NAMESPACE_CONFLICT_RISK', result['findings'])
        self.assertEqual(result['live_identity'], 'UNVERIFIED')
        hidden = self.snapshot(reference=AccountReference(store='LEGACY_DEMO', account_id='demo-sub-hidden',
                               revision=0, tenant_id='test-tenant'), nas=NasReference(router_id='demo-router-hidden'))
        with self.assertRaises(PermissionError):
            inspect_aaa_snapshot(snapshot, scope, (hidden,))

    def test_expiry_requires_explicit_policy_and_correct_exclusive_utc_boundary(self):
        boundary = datetime(2026, 12, 23, 21, tzinfo=timezone.utc)
        known = SubscriptionTerms(expires_on=date(2026, 12, 23), expires_at_utc=boundary,
                                  expiration_policy='END_OF_DAY_INCLUSIVE', account_status='ACTIVE')
        self.assertEqual(known.session_status, 'UNKNOWN')
        self.assertIsNone(SubscriptionTerms(expires_on=date(2026, 12, 23)).expires_at_utc)
        for changes in (dict(expiration_policy='UNDECIDED'),
                        dict(expires_at_utc=datetime(2026, 12, 24, tzinfo=timezone.utc)),
                        dict(expires_at_utc=datetime(2026, 12, 23, 21))):
            data = known.model_dump(); data.update(changes)
            with self.assertRaises(ValidationError):
                SubscriptionTerms(**data)

    def test_proof_is_actor_store_account_revision_and_content_bound_not_authorization(self):
        snapshot, scope = self.snapshot(), self.scope()
        proof = self.proof(snapshot)
        validate_preview_proof(snapshot, scope, proof)
        for changes in (dict(actor_id='other'), dict(account_id='demo-sub-other'), dict(expected_revision=1),
                        dict(store='PERSISTENT_WORKSPACE'), dict(snapshot_sha256='0' * 64)):
            with self.assertRaises(ValueError):
                validate_preview_proof(snapshot, scope, self.proof(snapshot, **changes))
        with self.assertRaises(PermissionError):
            validate_preview_proof(snapshot, self.scope(readable_router_ids=()), proof)
        self.assertEqual(compare_preview_proofs(proof, self.proof(snapshot)), 'MATCH')
        self.assertEqual(compare_preview_proofs(proof, self.proof(snapshot, actor_id='other')), 'CONFLICT')
        self.assertEqual(compare_preview_proofs(proof, self.proof(snapshot, request_id=UUID(int=3))), 'UNRELATED')

    def test_secret_and_write_inputs_rejected_frozen_roundtrip_and_hash_stable(self):
        snapshot = self.snapshot()
        for changes in (dict(external_writes=True), dict(password='SECRET_CANARY'), dict(attributes={'secret':'SECRET_CANARY'})):
            data = snapshot.model_dump(); data.update(changes)
            with self.assertRaises(ValidationError) as error:
                AaaSnapshot(**data)
            self.assertNotIn('SECRET_CANARY', str(error.exception))
        with self.assertRaises(ValidationError):
            snapshot.identity.realm = 'other'
        restored = AaaSnapshot.model_validate_json(snapshot.model_dump_json())
        self.assertEqual(snapshot_fingerprint(snapshot), snapshot_fingerprint(restored))
        self.assertEqual(inspect_aaa_snapshot(snapshot, self.scope()), inspect_aaa_snapshot(restored, self.scope()))
