"""End-to-end synthetic traces, no API/DB/device integration acceptance claims."""
from unittest import TestCase
from unittest.mock import patch
from datetime import timedelta
from pydantic import ValidationError
from app.simulation.aaa_transition import (
    SimulationRequest, SimulationResult, changed_request, changed_snapshot,
    synthetic_request, scenario_matrix, simulate_transition,
)


class MemoryAaaSimulation(TestCase):
    def test_matrix_is_deterministic_and_every_expected_blocker_is_observed_without_socket(self):
        with patch('socket.socket', side_effect=AssertionError('Network forbidden in memory simulation')):
            cases = scenario_matrix()
            self.assertEqual(len(cases), 20)
            for name, request, previous, expected, blocker in cases:
                with self.subTest(name=name):
                    before = request.model_dump_json()
                    old_receipt = previous.model_dump_json() if previous else None
                    result, receipt = simulate_transition(request, previous)
                    self.assertEqual(result.outcome, expected)
                    if blocker:
                        self.assertIn(blocker, result.blockers)
                    self.assertFalse(result.live_ready)
                    self.assertFalse(result.external_writes)
                    self.assertNotIn('Canlı geçişe hazır', result.model_dump_json())
                    self.assertEqual(request.model_dump_json(), before)
                    if previous:
                        self.assertEqual(previous.model_dump_json(), old_receipt)
                    self.assertEqual(simulate_transition(request, previous), (result, receipt))

    def test_success_only_describes_old_new_values_and_correlated_expected_audit(self):
        request = synthetic_request()
        result, _ = simulate_transition(request)
        self.assertEqual(result.outcome, 'PASS')
        self.assertEqual([(c.field, c.before, c.after) for c in result.planned_changes],
                         [('authority', 'LOCAL', 'RADIUS'), ('revision', 3, 4)])
        self.assertEqual(request.snapshot.authority, 'LOCAL')
        self.assertEqual(request.snapshot.reference.revision, 3)
        self.assertEqual(result.label, 'Sentetik simülasyon başarılı')
        self.assertTrue(all(e.origin == 'SIMULATED_EXPECTATION' and e.request_id == request.proof.request_id
                            and e.actor_id == request.scope.actor_id and e.occurred_at == request.clock
                            for e in result.expected_audit))
        self.assertEqual(len({e.event_id for e in result.expected_audit}), len(result.expected_audit))
        self.assertTrue(all('UNVERIFIED' in item for item in result.evidence[-1:]))

    def test_retry_returns_historical_receipt_before_revision_check_without_duplicate_audit(self):
        request = synthetic_request()
        first, receipt = simulate_transition(request)
        replay, same = simulate_transition(request, receipt)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.expected_audit, ())
        self.assertEqual(same, receipt)
        later, _ = simulate_transition(changed_request(request, clock=request.clock + timedelta(days=100)), receipt)
        self.assertTrue(later.replayed)  # Historical result, not a new expiry decision.
        self.assertEqual(later.expected_audit, ())
        data = request.snapshot.reference.model_dump(); data['revision'] = 4
        advanced = changed_request(request, snapshot=changed_snapshot(request.snapshot,
                    authority='RADIUS', reference=data))
        replay, _ = simulate_transition(advanced, receipt)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.simulated_final_revision, first.simulated_final_revision)
        stale, _ = simulate_transition(advanced)
        self.assertIn('STALE_OR_MISMATCHED_PROOF', stale.blockers)

    def test_uuid_conflict_preserves_first_receipt_and_does_not_plan_another_change(self):
        request = synthetic_request()
        _, receipt = simulate_transition(request)
        altered = changed_request(request, fail_at='AFTER_TARGET_STAGED')
        result, kept = simulate_transition(altered, receipt)
        self.assertEqual(result.outcome, 'BLOCKED')
        self.assertEqual(result.blockers, ('IDEMPOTENCY_CONFLICT',))
        self.assertEqual(result.planned_changes, ())
        self.assertEqual(kept, receipt)

    def test_partial_failure_compensates_only_in_trace_without_rewinding_revision(self):
        for failure, revision in [('AFTER_TARGET_STAGED', 3), ('AFTER_SOURCE_SWITCH', 5)]:
            request = synthetic_request(fail_at=failure)
            result, _ = simulate_transition(request)
            self.assertEqual(result.outcome, 'BLOCKED')
            self.assertEqual(result.simulated_final_authority, 'LOCAL')
            self.assertEqual(result.simulated_final_revision, revision)
            self.assertEqual(request.snapshot.reference.revision, 3)
            self.assertEqual(result.expected_audit[-1].phase, 'COMPENSATION_SUCCESS_MODELED')
        result, _ = simulate_transition(synthetic_request(fail_at='AFTER_SOURCE_SWITCH', compensation='BLOCKED'))
        self.assertIn('READ_ONLY_RECONCILIATION_REQUIRED', result.blockers)
        self.assertEqual(result.simulated_final_authority, 'RADIUS')
        self.assertEqual(result.simulated_final_revision, 4)
        self.assertIn('CAS_COMPENSATION_ONLY_IF_REVISION_MATCHES', result.rollback_plan)

    def test_scope_denial_never_exposes_plan_or_hidden_peer_details(self):
        request = synthetic_request()
        peer = changed_snapshot(request.snapshot, reference={**request.snapshot.reference.model_dump(),
                                'account_id': 'demo-sub-secret-peer'},
                                nas={**request.snapshot.nas.model_dump(), 'router_id': 'demo-router-hidden'})
        result, _ = simulate_transition(changed_request(request, peers=(peer,)))
        self.assertEqual(result.blockers, ('SCOPE_DENIED',))
        self.assertEqual(result.planned_changes, ())
        self.assertIsNone(result.simulated_final_authority)
        self.assertIsNone(result.expected_audit[0].account_id)
        self.assertNotIn('secret-peer', result.model_dump_json())

    def test_strict_simulation_cannot_accept_credentials_or_claim_live_success(self):
        request = synthetic_request()
        for changes in [dict(password='SYNTHETIC_SECRET_CANARY'), dict(fixture='LIVE')]:
            with self.assertRaises(ValidationError) as error:
                SimulationRequest(**{**request.model_dump(), **changes})
            self.assertNotIn('SYNTHETIC_SECRET_CANARY', str(error.exception))
        with self.assertRaises(ValidationError):
            SimulationResult(outcome='PASS', label='Sentetik simülasyon başarılı', live_ready=True)
