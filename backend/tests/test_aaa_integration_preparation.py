"""New preparation boundary only: synthetic input, no existing data or providers."""
from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID
from pydantic import ValidationError

from app.integrations.aaa_contracts import snapshot_fingerprint
from app.simulation.aaa_transition import synthetic_request
from app.simulation.aaa_integration_preparation import (
    FixtureGates, PreparationRequest, FixtureObservation, FakeAaaReadAdapter,
    prepare_handoff, compare_prepared_steps,
)


class IntegrationPreparationTests(TestCase):
    def setUp(self):
        preview = synthetic_request()
        self.scope = preview.scope
        self.request = PreparationRequest(preview=preview, correlation_id=UUID(int=901), phase='PREPARE',
            expected_operation_revision=1, expected_source_revision=7, expected_target_revision=0,
            gates=FixtureGates(snapshot_sha256=snapshot_fingerprint(preview.snapshot),
                actor_id=self.scope.actor_id, tenant_id=self.scope.tenant_id,
                valid_until=preview.clock + timedelta(minutes=5), namespace_revision=2,
                nas_revision=1, profile_revision=1, namespace_exclusive=True,
                credential_ownership_approved=True, disabled_target_supported=True,
                source_fencing_supported=True, atomic_owner_audit_supported=True))
        self.observation = FixtureObservation(snapshot_sha256=self.request.gates.snapshot_sha256,
            namespace_revision=2, account_revision=3, source_revision=7, target_revision=0,
            local_state='ENABLED', radius_state='ABSENT')
        # Hard guard for all new tests; only in-memory fake observations are permitted.
        for target in ('socket.socket', 'socket.create_connection', 'sqlite3.connect', 'psycopg.connect'):
            self.enterContext(patch(target, side_effect=AssertionError('External IO forbidden')))

    def run_step(self, *, phase='PREPARE', changes=None, request=None, permission=True):
        request = request or self.request.model_copy(update={'phase': phase})
        observation = self.observation.model_copy(update=changes or {})
        return prepare_handoff(request, self.scope, FakeAaaReadAdapter(observation),
                               fixture_transition_permission=permission)

    def test_forward_steps_only_enable_target_after_matching_source_fence(self):
        for phase, local, radius, fenced, expected in (
            ('PREPARE', 'ENABLED', 'ABSENT', False, 'STAGE_DISABLED_TARGET'),
            ('TARGET_STAGED', 'ENABLED', 'DISABLED', False, 'FENCE_LOCAL'),
            ('SOURCE_FENCED', 'DISABLED', 'DISABLED', True, 'ENABLE_RADIUS'),
            ('TARGET_ENABLED', 'DISABLED', 'ENABLED', True, 'COMMIT_OWNER_CAS'),
        ):
            with self.subTest(phase=phase):
                result = self.run_step(phase=phase, changes={'local_state': local, 'radius_state': radius,
                    'source_fenced': fenced, 'fence_request_id': self.request.preview.proof.request_id})
                self.assertEqual(result.action, expected)
                self.assertFalse(result.live_ready)
                self.assertFalse(result.external_writes)
                self.assertEqual(result.correlation_id, self.request.correlation_id)

    def test_permission_tenant_and_actor_denied_before_fake_read(self):
        with patch.object(FakeAaaReadAdapter, 'read', side_effect=AssertionError('Read before authorization')):
            self.assertEqual(self.run_step(permission=False).action, 'NONE')
            for change in ({'tenant_id': 'other'}, {'actor_id': 'other'}):
                scope = self.scope.model_copy(update=change)
                result = prepare_handoff(self.request, scope, FakeAaaReadAdapter(self.observation),
                                         fixture_transition_permission=True)
                self.assertEqual(result.action, 'NONE')

    def test_missing_stale_or_wrong_mapping_evidence_never_reaches_adapter(self):
        changes = [{flag: False} for flag in ('namespace_exclusive', 'credential_ownership_approved',
            'disabled_target_supported', 'source_fencing_supported', 'atomic_owner_audit_supported')]
        changes += [{'valid_until': self.request.preview.clock}, {'nas_revision': 2},
                    {'profile_revision': 2}, {'snapshot_sha256': '0' * 64}]
        with patch.object(FakeAaaReadAdapter, 'read', side_effect=AssertionError('Read before evidence')):
            for change in changes:
                request = self.request.model_copy(update={'gates': self.request.gates.model_copy(update=change)})
                self.assertEqual(self.run_step(request=request).action, 'NONE')

    def test_dual_authority_unknown_and_unfenced_states_require_reconciliation(self):
        for change in ({'radius_state': 'ENABLED'}, {'local_state': 'UNKNOWN'},
                       {'radius_state': 'UNKNOWN'}, {'local_state': 'DISABLED', 'radius_state': 'DISABLED'},
                       {'local_state': 'DISABLED', 'radius_state': 'DISABLED', 'source_fenced': True,
                        'fence_request_id': UUID(int=999)}):
            self.assertEqual(self.run_step(phase='SOURCE_FENCED', changes=change).action,
                             'READ_ONLY_RECONCILIATION')
        self.assertEqual(self.run_step(phase='UNCERTAIN').action, 'READ_ONLY_RECONCILIATION')

    def test_revision_drift_blocks_both_activation_and_compensation(self):
        for phase in ('SOURCE_FENCED', 'COMPENSATING'):
            for change in ({'source_revision': 8}, {'target_revision': 1},
                           {'account_revision': 4}, {'namespace_revision': 3}, {'snapshot_sha256': '0' * 64}):
                result = self.run_step(phase=phase, changes={**change, 'local_state': 'DISABLED',
                    'radius_state': 'DISABLED', 'source_fenced': True,
                    'fence_request_id': self.request.preview.proof.request_id})
                self.assertEqual(result.reason, 'REVISION_OR_OBSERVATION_CONFLICT')
                self.assertEqual(result.action, 'READ_ONLY_RECONCILIATION')

    def test_compensation_disables_target_before_restoring_local_and_never_rewinds_account(self):
        for local, radius, action in (('DISABLED', 'ENABLED', 'DISABLE_RADIUS'),
            ('DISABLED', 'DISABLED', 'RESTORE_LOCAL'), ('ENABLED', 'DISABLED', 'COMPLETE_COMPENSATION')):
            observation = {'local_state': local, 'radius_state': radius, 'source_fenced': True,
                           'fence_request_id': self.request.preview.proof.request_id}
            self.assertEqual(self.run_step(phase='COMPENSATING', changes=observation).action, action)
        self.assertEqual(self.request.preview.snapshot.reference.revision, 3)
        self.assertEqual(self.request.preview.snapshot.authority, 'LOCAL')

    def test_step_fingerprint_binds_policy_correlation_observation_and_operation_revision(self):
        first = self.run_step()
        self.assertEqual(compare_prepared_steps(first, self.run_step()), 'MATCH')
        for changes in ({'correlation_id': UUID(int=902)},
                        {'gates': self.request.gates.model_copy(update={'namespace_revision': 3})}):
            altered = self.run_step(request=self.request.model_copy(update=changes))
            self.assertEqual(compare_prepared_steps(first, altered), 'CONFLICT')
        observed = self.run_step(changes={'radius_state': 'DISABLED'})
        self.assertNotEqual(first.fingerprint, observed.fingerprint)
        self.assertEqual(compare_prepared_steps(first, observed), 'CONFLICT')
        next_step = self.run_step(request=self.request.model_copy(update={'expected_operation_revision': 2}))
        self.assertEqual(compare_prepared_steps(first, next_step), 'DIFFERENT_STEP')
        self.assertEqual(first.event_id, self.run_step().event_id)

    def test_real_adapter_and_secret_or_live_claims_rejected_without_io(self):
        class NotAFake:
            def read(self):
                raise AssertionError('A real adapter must never be invoked')
        with self.assertRaises(TypeError):
            prepare_handoff(self.request, self.scope, NotAFake(), fixture_transition_permission=True)
        for change in ({'password': 'forbidden-fixture-input'}, {'origin': 'LIVE_VERIFIED'}):
            with self.assertRaises(ValidationError):
                FixtureGates(**{**self.request.gates.model_dump(), **change})
        before = self.request.model_dump_json(), self.observation.model_dump_json()
        self.run_step()
        self.assertEqual(before, (self.request.model_dump_json(), self.observation.model_dump_json()))
