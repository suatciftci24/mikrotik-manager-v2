"""End-to-end acceptance using real memory services and the existing synthetic builder."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from uuid import UUID
from backend.tests import test_aaa_next_step_executor as fx
from app.simulation.aaa_next_step_preparation import NextStepPreparationService
from app.simulation.aaa_prepared_authorization import PreparedExecutionService


class AaaE2eAcceptance(TestCase):
    def begin(self):
        # Existing builder executes root plan/lease/provider/UNKNOWN/decision/CONTINUE,
        # not mocked return values or direct state seeding.
        self.f=fx.NextStepExecutorTests(methodName='runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        f=self.f
        self.root_history=f.unit.snapshot()
        self.assertEqual(f.root.plan_hash(),f.request.plan.plan_hash())
        self.assertEqual(next(iter(f.unit._state['journal'].values())).state,'EXECUTOR_CONTINUE_HELD')
        self.first=f.stage(f.issue(plan=f.plan('ENABLE_RADIUS'),number=5000))
        self.executor=fx.FixtureExecutor(f.unit,f.provider,outcome='SUCCESS')
        self.runner=fx.ExecutorContext(tenant_id=f.root.tenant_id,worker_id='e2e',can_execute=True,can_accept=True,can_record_timeout=True)
        self.first_command=self.claim(self.first.authorization_id,5100)
        with self.assertRaises(fx.FixtureCrash): self.run_fake(self.first_command,crash='AFTER_EFFECT')
        f.clock.advance(30)
        self.unknown=self.executor.timeout(f.request,f.scope,self.runner,self.first_command,permission=True)
        before=self.snapshot()
        evaluation=f.service.evaluate(f.request,f.scope,f.context,self.first_command.execution_id,permission=True)
        self.assertEqual(evaluation.status,'CONFIRMED_SUCCESS')
        self.assertEqual(before,self.snapshot())
        grant=f.service.issue(f.request,f.scope,f.context,evaluation,
            fx.ExecutorDecisionIntent(authorization_id=UUID(int=5200),decision='CONFIRM_SUCCESS'),permission=True)
        self.decision=f.service.apply(f.request,f.scope,f.context,grant,permission=True)
        self.assertEqual(self.decision.state,'NEXT_STEP_DECISION_RECORDED')
        return f

    def snapshot(self): return self.f.unit.snapshot(),self.f.provider.snapshot()
    def claim(self, execution, attempt=5500):
        f=self.f
        return self.executor.claim(f.request,f.scope,self.runner,execution,fx.AttemptIntent(attempt_id=UUID(int=attempt)),permission=True)
    def run_fake(self, command, **kwargs):
        f=self.f
        return self.executor.run(f.request,f.scope,self.runner,command,permission=True,**kwargs)
    def accept(self, receipt, **kwargs):
        f=self.f
        return self.executor.accept(f.request,f.scope,self.runner,receipt,permission=True,**kwargs)

    def policy(self, kind='CONTINUE'):
        f=self.f
        plan=f.policy.plan(f.request,f.scope,self.decision.authorization_id,kind,permission=True)
        grant=f.policy.issue(f.request,f.scope,f.authority,plan,fx.ExecutorPolicyIntent(authorization_id=UUID(int=5300)),permission=True)
        self.policy_record=f.policy.apply(f.request,f.scope,f.authority,grant,permission=True)

    def authorize_final(self, outcome='SUCCESS', seconds=60):
        f=self.f
        self.policy()
        preparation=NextStepPreparationService(f.unit,f.provider)
        plan=preparation.plan(f.request,f.scope,self.policy_record.authorization_id,'COMMIT_OWNER_CAS',permission=True)
        grant=preparation.issue(f.request,f.scope,f.execution_authority,plan,fx.ExecutionIntent(authorization_id=UUID(int=5400)),permission=True)
        self.prepared=preparation.prepare(f.request,f.scope,f.execution_authority,grant,permission=True)
        self.assertEqual(self.prepared.state,'NEXT_STEP_PREPARED_HELD')
        service=PreparedExecutionService(f.unit,f.provider)
        plan=service.plan(f.request,f.scope,self.prepared.authorization_id,'COMMIT_OWNER_CAS',permission=True)
        grant=service.issue(f.request,f.scope,f.execution_authority,plan,
            fx.ExecutionIntent(authorization_id=UUID(int=5450),lifetime_seconds=seconds),permission=True)
        self.authorized=service.consume(f.request,f.scope,f.execution_authority,grant,permission=True)
        self.assertEqual(self.authorized.state,'EXECUTION_AUTHORIZED_HELD')
        self.executor=fx.FixtureExecutor(f.unit,f.provider,outcome=outcome)
        self.final_history=f.unit.snapshot()
        return grant

    def assert_preserved(self):
        state=self.f.unit.snapshot()
        for prior in (self.root_history,self.final_history):
            for table in ('execution_records','executor_accepted','executor_decision_records','executor_policy_records'):
                for key,value in prior[table].items(): self.assertEqual(state[table][key],value)
        self.assertEqual(self.final_history['audit'],state['audit'][:len(self.final_history['audit'])])
        self.assertEqual(state['executor_accepted'][self.first_command.execution_id],self.unknown)

    def test_complete_chain_success_rejected_unknown_and_final_unknown_decision(self):
        for outcome in ('SUCCESS','REJECTED','UNKNOWN'):
            with self.subTest(outcome=outcome):
                f=self.begin()
                grant=self.authorize_final(outcome)
                receipt=self.run_fake(self.claim(grant.authorization_id))
                result=self.accept(receipt)
                self.assertEqual(result.state,{'SUCCESS':'FIXTURE_STEP_SUCCEEDED','REJECTED':'FIXTURE_STEP_REJECTED','UNKNOWN':'FIXTURE_STEP_UNKNOWN'}[outcome])
                owner=next(iter(f.unit._state['owners'].values()))
                self.assertEqual(owner.authority,'RADIUS' if outcome=='SUCCESS' else 'LOCAL')
                self.assert_preserved()
                self.assertFalse(any(e.status=='PENDING' for e in next(iter(f.unit._state['outbox'].values()))))
        # A lost definitive response also traverses the new prepared evaluator/decision bridge.
        f=self.begin();grant=self.authorize_final()
        command=self.claim(grant.authorization_id)
        with self.assertRaises(fx.FixtureCrash): self.run_fake(command,crash='AFTER_EFFECT')
        f.clock.advance(30)
        accepted=self.executor.timeout(f.request,f.scope,self.runner,command,permission=True)
        evaluation=f.service.evaluate(f.request,f.scope,f.context,command.execution_id,permission=True)
        self.assertEqual(evaluation.status,'CONFIRMED_SUCCESS')
        decision=f.service.issue(f.request,f.scope,f.context,evaluation,
            fx.ExecutorDecisionIntent(authorization_id=UUID(int=5600),decision='CONFIRM_SUCCESS'),permission=True)
        record=f.service.apply(f.request,f.scope,f.context,decision,permission=True)
        self.assertEqual(record.state,'NEXT_STEP_DECISION_RECORDED')
        self.assertEqual(f.unit._state['executor_accepted'][command.execution_id],accepted)
        self.assertEqual(next(iter(f.unit._state['owners'].values())).authority,'LOCAL')
        self.assert_preserved()

    def test_cancel_blocks_preparation_and_execution(self):
        f=self.begin();self.policy('CANCEL')
        before=self.snapshot()
        with self.assertRaises(fx.AtomicConflict):
            NextStepPreparationService(f.unit,f.provider).plan(f.request,f.scope,self.policy_record.authorization_id,'COMMIT_OWNER_CAS',permission=True)
        with self.assertRaises(fx.AtomicConflict): self.claim(self.first.authorization_id,9999)
        self.assertEqual(before,self.snapshot())

    def test_concurrency_replay_and_provider_after_record_failure(self):
        f=self.begin();grant=self.authorize_final()
        with ThreadPoolExecutor(max_workers=2) as pool:
            commands=list(pool.map(lambda _:self.claim(grant.authorization_id),range(2)))
        self.assertEqual(commands[0],commands[1])
        command=commands[0]
        with ThreadPoolExecutor(max_workers=2) as pool: receipts=list(pool.map(lambda _:self.run_fake(command),range(2)))
        self.assertEqual(receipts[0],receipts[1])
        before=self.snapshot()
        with self.assertRaises(fx.AtomicConflict): self.accept(receipts[0],fail_at='AUDIT')
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.run_fake(command),receipts[0])
        self.assertEqual(before,self.snapshot())
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:self.accept(receipts[0]),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(sum(r[:3]==(command.execution_id,command.attempt_id,'STARTED') for r in f.unit._state['executor_audit']),1)
        self.assert_preserved()

    def test_expired_authority_and_stale_cas_fence_reject(self):
        f=self.begin();grant=self.authorize_final(seconds=2)
        f.clock.advance(2)
        before=self.snapshot()
        with self.assertRaises(fx.AtomicConflict): self.claim(grant.authorization_id)
        self.assertEqual(before,self.snapshot())
        f=self.begin();grant=self.authorize_final()
        original=self.snapshot()
        for table,field in [('owners','revision'),('leases','token')]:
            f.unit._state=deepcopy(original[0]);f.provider._state=deepcopy(original[1])
            key,value=next(iter(f.unit._state[table].items()))
            f.unit._state[table][key]=value.model_copy(update={field:getattr(value,field)+1})
            before=self.snapshot()
            with self.assertRaises(fx.AtomicConflict): self.claim(grant.authorization_id)
            self.assertEqual(before,self.snapshot())

    def test_wrong_scope_plan_step_or_receipt_reject(self):
        f=self.begin();grant=self.authorize_final();command=self.claim(grant.authorization_id)
        before=self.snapshot()
        for changes in ({'tenant_id':'wrong'},{'subscriber_id':'wrong'},{'execution_id':UUID(int=99)},
                        {'plan_hash':'0'*64},{'allowed_step':'ENABLE_RADIUS'}):
            with self.assertRaises(fx.AtomicConflict): self.run_fake(command.model_copy(update=changes))
            self.assertEqual(before,self.snapshot())
        receipt=self.run_fake(command)
        before=self.snapshot()
        with self.assertRaises(fx.AtomicConflict): self.accept(receipt.model_copy(update={'attempt_id':UUID(int=99)}))
        self.assertEqual(before,self.snapshot())

    def test_unknown_no_retry_and_missing_contradictory_nonindependent_evidence(self):
        f=self.begin();grant=self.authorize_final('UNKNOWN');command=self.claim(grant.authorization_id)
        accepted=self.accept(self.run_fake(command))
        original=self.snapshot()
        for kind in ('UNKNOWN','MISSING','DERIVED','CONTRADICTORY'):
            f.unit._state=deepcopy(original[0]);f.provider._state=deepcopy(original[1])
            if kind=='MISSING': del f.provider._state['executor_receipts'][command.execution_id]
            elif kind=='DERIVED': f.provider._state['executor_receipts'][command.execution_id]=accepted.receipt.model_copy(update={'outcome':'SUCCESS'})
            elif kind=='CONTRADICTORY':
                current=f.provider._state['provider'];f.provider._state['provider']=current.model_copy(update={'generation':999})
            before=self.snapshot()
            evaluation=f.service.evaluate(f.request,f.scope,f.context,command.execution_id,permission=True)
            self.assertEqual(evaluation.status,'READ_ONLY_RECONCILIATION_REQUIRED')
            with self.assertRaises(fx.AtomicConflict): self.run_fake(command)
            with self.assertRaises(fx.AtomicConflict): self.claim(grant.authorization_id,attempt=9999)
            self.assertEqual(before,self.snapshot())
