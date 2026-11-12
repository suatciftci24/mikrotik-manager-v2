"""New authorized-held execution tests only; builders use memory fake provider."""
from copy import deepcopy
from unittest import TestCase
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID
from backend.tests import test_aaa_next_step_preparation as fixtures
from app.simulation.aaa_prepared_authorization import PreparedExecutionService
from app.simulation.aaa_execution import ExecutionIntent
from app.simulation.aaa_executor import FixtureExecutor, AttemptIntent, FixtureCrash, ExecutorReceipt
from app.simulation.aaa_atomic import AtomicConflict


class PreparedExecutorTests(TestCase):
    def setup_fixture(self, outcome='SUCCESS', seconds=60):
        helper=fixtures.NextStepPreparationTests(methodName='runTest')
        self.addCleanup(helper.doCleanups)
        self.f=helper.setup_fixture()
        self.prepared=helper.prepare(helper.issue())
        f=self.f
        service=PreparedExecutionService(f.unit,f.provider)
        plan=service.plan(f.request,f.scope,self.prepared.authorization_id,'COMMIT_OWNER_CAS',permission=True)
        self.grant=service.issue(f.request,f.scope,f.execution_authority,plan,
            ExecutionIntent(authorization_id=UUID(int=10000),lifetime_seconds=seconds),permission=True)
        self.authorized=service.consume(f.request,f.scope,f.execution_authority,self.grant,permission=True)
        self.executor=FixtureExecutor(f.unit,f.provider,outcome=outcome)
        self.history=f.unit.snapshot()
        return f

    def claim(self, attempt=10100):
        f=self.f
        return self.executor.claim(f.request,f.scope,f.runner,self.grant.authorization_id,
            AttemptIntent(attempt_id=UUID(int=attempt),seconds=30),permission=True)

    def run_fake(self, command, **kwargs):
        f=self.f
        return self.executor.run(f.request,f.scope,f.runner,command,permission=True,**kwargs)

    def accept(self, receipt, **kwargs):
        f=self.f
        return self.executor.accept(f.request,f.scope,f.runner,receipt,permission=True,**kwargs)

    def snapshot(self): return self.f.unit.snapshot(),self.f.provider.snapshot()

    def assert_history(self):
        state=self.f.unit.snapshot()
        for table in ('executor_accepted','executor_decision_records','executor_policy_records','execution_records'):
            for key,value in self.history[table].items(): self.assertEqual(state[table][key],value)
        self.assertEqual(state['executor_decision_audit'],self.history['executor_decision_audit'])
        self.assertEqual(state['executor_policy_audit'],self.history['executor_policy_audit'])

    def test_success_rejection_unknown_use_existing_receipts_without_next_dispatch(self):
        for outcome in ('SUCCESS','REJECTED','UNKNOWN'):
            f=self.setup_fixture(outcome)
            command=self.claim()
            receipt=self.run_fake(command)
            self.assertEqual(ExecutorReceipt.model_validate_json(receipt.model_dump_json()),receipt)
            self.assertEqual(receipt.outcome,outcome)
            accepted=self.accept(receipt)
            self.assertEqual(accepted.state,{'SUCCESS':'FIXTURE_STEP_SUCCEEDED','REJECTED':'FIXTURE_STEP_REJECTED','UNKNOWN':'FIXTURE_STEP_UNKNOWN'}[outcome])
            owner=next(iter(f.unit._state['owners'].values()))
            self.assertEqual(owner.authority,'RADIUS' if outcome=='SUCCESS' else 'LOCAL')
            if outcome=='UNKNOWN':
                self.assertEqual(accepted.reconciliation_reference.execution_plan_contract,'PREPARED_EXECUTION_PLAN_V1_FIXTURE')
                before=self.snapshot()
                evidence=self.executor.unknown_evidence(f.request,f.scope,f.runner,command.execution_id,permission=True)
                self.assertEqual(evidence['accepted'],accepted)
                evaluation=f.service.evaluate(f.request,f.scope,f.context,command.execution_id,permission=True)
                self.assertEqual(evaluation.status,'READ_ONLY_RECONCILIATION_REQUIRED')
                self.assertEqual(evaluation.receipt_fingerprint,accepted.reconciliation_reference.receipt_fingerprint)
                self.assertEqual(before,self.snapshot())
            self.assertFalse(any(e.status=='PENDING' for e in next(iter(f.unit._state['outbox'].values()))))
            self.assert_history()

    def test_concurrent_claim_run_and_accept_execute_once_and_replay_idempotent(self):
        f=self.setup_fixture()
        with ThreadPoolExecutor(max_workers=2) as pool: commands=list(pool.map(lambda _:self.claim(),range(2)))
        self.assertEqual(commands[0],commands[1])
        command=commands[0]
        with ThreadPoolExecutor(max_workers=2) as pool: receipts=list(pool.map(lambda _:self.run_fake(command),range(2)))
        self.assertEqual(receipts[0],receipts[1])
        self.assertEqual(sum(r[:3]==(command.execution_id,command.attempt_id,'STARTED') for r in f.unit._state['executor_audit']),1)
        with ThreadPoolExecutor(max_workers=2) as pool: accepted=list(pool.map(lambda _:self.accept(receipts[0]),range(2)))
        self.assertEqual(accepted[0],accepted[1])
        self.assert_history()

    def test_prepared_only_expired_wrong_scope_and_stale_fence_block_before_run(self):
        f=self.setup_fixture(seconds=2)
        before=self.snapshot()
        with self.assertRaises(AtomicConflict):
            self.executor.claim(f.request,f.scope,f.runner,self.prepared.authorization_id,AttemptIntent(attempt_id=UUID(int=10100)),permission=True)
        with self.assertRaises(PermissionError):
            self.executor.claim(f.request,f.scope,f.runner.model_copy(update={'can_execute':False}),self.grant.authorization_id,AttemptIntent(attempt_id=UUID(int=10100)),permission=True)
        self.assertEqual(before,self.snapshot())
        command=self.claim()
        self.assertEqual(command.expires_at,self.grant.expires_at)
        f.clock.advance(2)
        before=self.snapshot()
        with self.assertRaises(AtomicConflict): self.run_fake(command)
        self.assertEqual(before,self.snapshot())

    def test_claim_and_receipt_content_versions_and_attempt_mismatch_fail_closed(self):
        self.setup_fixture()
        command=self.claim()
        before=self.snapshot()
        for change in ({'attempt_id':UUID(int=1)},{'contract_version':'wrong'},{'fencing_token':1},{'plan_hash':'0'*64},{'allowed_step':'ENABLE_RADIUS'}):
            with self.assertRaises(AtomicConflict): self.run_fake(command.model_copy(update=change))
            self.assertEqual(before,self.snapshot())
        receipt=self.run_fake(command)
        before=self.snapshot()
        for change in ({'receipt_version':'wrong'},{'attempt_id':UUID(int=1)},{'provider_evidence_fingerprint':'0'*64},{'outcome':'REJECTED'}):
            with self.assertRaises(AtomicConflict): self.accept(receipt.model_copy(update=change))
            self.assertEqual(before,self.snapshot())

    def test_five_atomic_accept_faults_never_redispatch(self):
        f=self.setup_fixture()
        command=self.claim()
        receipt=self.run_fake(command)
        before=self.snapshot()
        for fault in ('OWNER','JOURNAL','AUDIT','OUTBOX','AUTHORIZATION'):
            with self.assertRaises(AtomicConflict): self.accept(receipt,fail_at=fault)
            self.assertEqual(before,self.snapshot())
        self.assertEqual(self.run_fake(command),receipt) # Cached receipt, no second STARTED/provider invocation.
        self.assertEqual(before,self.snapshot())
        self.accept(receipt)

    def test_after_dispatch_crash_and_lost_response_keep_unknown_without_retry(self):
        for crash in ('AFTER_DISPATCH','AFTER_EFFECT'):
            f=self.setup_fixture(seconds=2)
            command=self.claim()
            with self.assertRaises(FixtureCrash): self.run_fake(command,crash=crash)
            f.clock.advance(2)
            accepted=self.executor.timeout(f.request,f.scope,f.runner,command,permission=True)
            self.assertEqual(accepted.receipt.outcome,'UNKNOWN')
            self.assertIsNotNone(accepted.reconciliation_reference)
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.run_fake(command)
            with self.assertRaises(AtomicConflict): self.claim(attempt=10101)
            self.assertEqual(before,self.snapshot())
            self.assert_history()

    def test_provider_fence_drift_and_post_effect_cas_failure_do_not_retry(self):
        for drift in ('PROVIDER','OWNER'):
            f=self.setup_fixture()
            command=self.claim()
            receipt=self.run_fake(command)
            if drift=='PROVIDER': f.provider._state['highest']=(command.owner_fence,command.fencing_token+1)
            else:
                key,owner=next(iter(f.unit._state['owners'].items()))
                f.unit._state['owners'][key]=owner.model_copy(update={'revision':owner.revision+1})
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.accept(receipt)
            with self.assertRaises(AtomicConflict): self.run_fake(command)
            self.assertEqual(before,self.snapshot())
            self.assertNotIn(command.execution_id,f.unit._state['executor_accepted'])

    def test_stale_before_effect_expired_authority_and_tampered_staging_reject(self):
        for kind in ('EXPIRED','FENCE','VERSION','HISTORY','UNKNOWN'):
            f=self.setup_fixture(seconds=2)
            if kind=='EXPIRED': f.clock.advance(2)
            elif kind=='FENCE': f.provider._state['highest']=(999,999)
            elif kind=='VERSION':
                f.unit._state['execution_authorizations'][self.grant.authorization_id]=self.grant.model_copy(update={'version':'wrong'})
            elif kind=='HISTORY':
                del f.unit._state['execution_records'][self.prepared.authorization_id]
            else:
                key,op=next(iter(f.unit._state['journal'].items()))
                f.unit._state['journal'][key]=op.model_copy(update={'state':'FIXTURE_STEP_UNKNOWN'})
            before=self.snapshot()
            with self.assertRaises((AtomicConflict,KeyError)): self.claim()
            self.assertEqual(before,self.snapshot())
