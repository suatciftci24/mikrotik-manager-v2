"""Read-only independent prepared-execution evidence, no old suite rerun."""
from copy import deepcopy
from unittest import TestCase
from uuid import UUID
from backend.tests import test_aaa_prepared_executor as fixtures
from app.simulation.aaa_executor import FixtureCrash
from app.simulation.aaa_executor_decision import ExecutorDecisionIntent, ExecutorReconciliationService
from app.simulation.aaa_provider import FakeFencedProvider
from app.simulation.aaa_atomic import AtomicConflict


class PreparedEvidenceTests(TestCase):
    def setup_fixture(self, outcome='SUCCESS', crash='AFTER_EFFECT'):
        helper=fixtures.PreparedExecutorTests(methodName='runTest')
        self.addCleanup(helper.doCleanups)
        self.f=helper.setup_fixture(outcome=outcome,seconds=2)
        self.command=helper.claim()
        try: helper.run_fake(self.command,crash=crash)
        except FixtureCrash: pass
        self.f.clock.advance(2)
        f=self.f
        self.accepted=helper.executor.timeout(f.request,f.scope,f.runner,self.command,permission=True)
        return f

    def evaluate(self):
        f=self.f
        before=f.unit.snapshot(),f.provider.snapshot()
        result=f.service.evaluate(f.request,f.scope,f.context,self.command.execution_id,permission=True)
        self.assertEqual(before,(f.unit.snapshot(),f.provider.snapshot()))
        self.assertFalse(result.decision_authority)
        self.assertFalse(result.automatic_dispatch)
        return result

    def test_definitive_independent_success_and_rejection_preserve_unknown(self):
        for outcome in ('SUCCESS','REJECTED'):
            self.setup_fixture(outcome)
            result=self.evaluate()
            self.assertEqual(result.status,'CONFIRMED_SUCCESS' if outcome=='SUCCESS' else 'CONFIRMED_REJECTION')
            ref=self.accepted.reconciliation_reference
            for field in ('tenant_id','subscriber_id','execution_id','event_id','attempt_id','plan_hash',
                          'owner_revision','fencing_token','receipt_fingerprint','execution_plan_contract'):
                self.assertEqual(getattr(result,field),getattr(ref,field))
            self.assertEqual(result.version,ref.evaluation_contract)
            self.assertEqual(self.f.unit._state['executor_accepted'][self.command.execution_id],self.accepted)
            before=self.f.unit.snapshot(),self.f.provider.snapshot()
            with self.assertRaises(PermissionError):
                self.f.service.issue(self.f.request,self.f.scope,self.f.context.model_copy(update={'can_issue_decision':False}),result,
                    ExecutorDecisionIntent(authorization_id=UUID(int=11000),decision='CONFIRM_SUCCESS' if outcome=='SUCCESS' else 'CONFIRM_REJECTION'),permission=True)
            self.assertEqual(before,(self.f.unit.snapshot(),self.f.provider.snapshot()))

    def test_unknown_missing_or_local_receipt_is_not_independent_evidence(self):
        f=self.setup_fixture()
        original=deepcopy(f.provider._state)
        for kind in ('MISSING','LOCAL_UNKNOWN','UNKNOWN_OUTCOME'):
            f.provider._state=deepcopy(original)
            if kind=='MISSING': del f.provider._state['executor_receipts'][self.command.execution_id]
            elif kind=='LOCAL_UNKNOWN': f.provider._state['executor_receipts'][self.command.execution_id]=self.accepted.receipt
            else:
                known=f.provider._state['executor_receipts'][self.command.execution_id]
                f.provider._state['executor_receipts'][self.command.execution_id]=known.model_copy(update={'outcome':'UNKNOWN'})
            self.assertEqual(self.evaluate().status,'READ_ONLY_RECONCILIATION_REQUIRED')

    def test_reference_binding_and_contract_tampering_fail_closed(self):
        f=self.setup_fixture()
        ref=self.accepted.reconciliation_reference
        for field,value in [('tenant_id','wrong'),('subscriber_id','wrong'),('execution_id',UUID(int=1)),
                            ('attempt_id',UUID(int=1)),('event_id',UUID(int=1)),('plan_hash','0'*64),
                            ('receipt_fingerprint','0'*64),('owner_revision',1),('fencing_token',1),
                            ('execution_plan_contract','wrong'),('version','wrong')]:
            f.unit._state['executor_accepted'][self.command.execution_id]=self.accepted.model_copy(update={
                'reconciliation_reference':ref.model_copy(update={field:value})})
            self.assertEqual(self.evaluate().status,'READ_ONLY_RECONCILIATION_REQUIRED')

    def test_independent_receipt_wrong_scope_step_version_or_fingerprint_rejected(self):
        f=self.setup_fixture()
        known=f.provider._state['executor_receipts'][self.command.execution_id]
        for field,value in [('tenant_id','wrong'),('subscriber_id','wrong'),('execution_id',UUID(int=1)),
                            ('attempt_id',UUID(int=1)),('allowed_step','ENABLE_RADIUS'),('owner_revision',1),
                            ('fencing_token',1),('receipt_version','wrong'),('provider_evidence_fingerprint','0'*64)]:
            f.provider._state['executor_receipts'][self.command.execution_id]=known.model_copy(update={field:value})
            self.assertEqual(self.evaluate().status,'READ_ONLY_RECONCILIATION_REQUIRED')

    def test_stale_contradictory_duplicate_or_missing_history_fail_closed(self):
        f=self.setup_fixture()
        original=f.unit.snapshot(),f.provider.snapshot()
        for kind in ('FENCE','OWNER','PROVIDER','DUPLICATE_AUDIT','HISTORY','EVENT'):
            f.unit._state=deepcopy(original[0]);f.provider._state=deepcopy(original[1])
            if kind=='FENCE': f.provider._state['highest']=(999,999)
            elif kind=='OWNER':
                key,owner=next(iter(f.unit._state['owners'].items()))
                f.unit._state['owners'][key]=owner.model_copy(update={'revision':owner.revision+1})
            elif kind=='PROVIDER':
                current=f.provider._state['provider']
                f.provider._state['provider']=current.model_copy(update={'generation':current.generation+1})
            elif kind=='DUPLICATE_AUDIT':
                f.unit._state['executor_audit'].append(next(r for r in f.unit._state['executor_audit'] if r[:3]==(self.command.execution_id,self.command.attempt_id,'STARTED')))
            elif kind=='HISTORY':
                del f.unit._state['execution_records'][self.f.unit._state['execution_authorizations'][self.command.execution_id].plan.preparation_id]
            else:
                key=next(iter(f.unit._state['outbox']))
                events=f.unit._state['outbox'][key]
                f.unit._state['outbox'][key]=events+(events[-1],)
            self.assertEqual(self.evaluate().status,'READ_ONLY_RECONCILIATION_REQUIRED')

    def test_foreign_reader_permissions_and_lost_dispatch_remain_unconfirmed(self):
        f=self.setup_fixture()
        foreign=FakeFencedProvider(f.root)
        foreign._state=deepcopy(f.provider._state)
        reader=ExecutorReconciliationService(f.unit,foreign,initialize=False)
        before=f.unit.snapshot(),foreign.snapshot()
        self.assertEqual(reader.evaluate(f.request,f.scope,f.context,self.command.execution_id,permission=True).status,'READ_ONLY_RECONCILIATION_REQUIRED')
        self.assertEqual(before,(f.unit.snapshot(),foreign.snapshot()))
        with self.assertRaises(PermissionError):
            f.service.evaluate(f.request,f.scope,f.context.model_copy(update={'can_evaluate':False}),self.command.execution_id,permission=True)
        # No successful fake response exists when dispatch itself was interrupted.
        self.setup_fixture(crash='AFTER_DISPATCH')
        self.assertEqual(self.evaluate().status,'READ_ONLY_RECONCILIATION_REQUIRED')

    def test_derived_unknown_claim_duplicate_or_missing_dispatch_provenance_rejected(self):
        f=self.setup_fixture(outcome='UNKNOWN')
        # Even moving a local UNKNOWN-derived assertion into the pinned reader map
        # cannot replace its independently recorded UNKNOWN dispatch outcome.
        f.provider._state['executor_receipts'][self.command.execution_id]=self.accepted.receipt.model_copy(update={'outcome':'SUCCESS'})
        self.assertEqual(self.evaluate().status,'READ_ONLY_RECONCILIATION_REQUIRED')
        f=self.setup_fixture()
        original=f.provider.snapshot()
        for kind in ('DUPLICATE','MISSING_PROVENANCE'):
            f.provider._state=deepcopy(original)
            if kind=='DUPLICATE':
                f.provider._state['executor_receipts'][UUID(int=333)]=f.provider._state['executor_receipts'][self.command.execution_id]
            else:
                del f.provider._state['executor_evidence'][self.command.execution_id]
            self.assertEqual(self.evaluate().status,'READ_ONLY_RECONCILIATION_REQUIRED')
