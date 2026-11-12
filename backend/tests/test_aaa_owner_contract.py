"""Common owner contract tests; fake locking is not PostgreSQL locking acceptance."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from uuid import UUID
from sqlalchemy import update
from backend.tests import test_aaa_metadata_repository as fixtures
from app.repositories.aaa_owner_contract import *
from app.repositories.aaa_metadata import owner, MetadataConflict, PostgresMetadataUow


class OwnerContractTests(TestCase):
    def setUp(self):
        self.helper=fixtures.MetadataRepositoryTests(methodName='runTest')
        self.helper.setUp();self.addCleanup(self.helper.doCleanups)
        self.scope=self.helper.scope
        self.grant=OwnershipGrant(**self.scope.model_dump(),actor_active=True,membership_revision=1,
                                  capabilities=('AAA_METADATA','DAILY_OWNER'))

    def test_wrong_tenant_actor_subscriber_inactive_or_unverified_grant_rejected(self):
        for change in ({'tenant_id':UUID(int=1)},{'actor_id':'foreign'},{'subscriber_id':'wrong'},
                       {'actor_active':False},{'capabilities':()},{'membership_revision':0},{'version':'wrong'}):
            with self.assertRaises(PermissionError):require_ownership(self.scope,self.grant.model_copy(update=change))
        for grant in (True,None,{'actor_id':self.scope.actor_id}):
            with self.assertRaises(PermissionError):require_ownership(self.scope,grant)
        require_ownership(self.scope,self.grant)

    def test_missing_metadata_wrong_identity_stale_revision_and_fencing(self):
        h=self.helper;row=h.db.state['subscribers'][0]
        for field in ('tenant_id','id','revision','source','aaa_fence','aaa_active_operation'):
            bad=dict(row);del bad[field]
            with self.assertRaises(OwnerContractConflict):locked_owner(bad,self.scope,operation_id=h.request.request_id,expected=h.old)
        for field,value in [('revision',99),('aaa_fence',99),('tenant_id',UUID(int=1)),('id','wrong'),('revision',True)]:
            with self.assertRaises(OwnerContractConflict):locked_owner({**row,field:value},self.scope,operation_id=h.request.request_id,expected=h.old)

    def test_daily_writer_cannot_bypass_active_aaa_lock_even_using_stale_read(self):
        h=self.helper
        with self.assertRaises(OwnerContractConflict):locked_owner(h.db.state['subscribers'][0],self.scope,operation_id=None,writer='DAILY_OWNER')
        unlocked=h.old.model_copy(update={'active_request':None})
        predicates=owner_cas_predicates(owner,self.scope,unlocked,operation_id=None,writer='DAILY_OWNER')
        before=deepcopy(h.db.state)
        with h.db.session() as session:
            with session.begin():
                changed=session.execute(update(owner).where(*predicates).values(revision=4,aaa_fence=6))
                self.assertEqual(changed.rowcount,0)
        self.assertEqual(before,h.db.state)

    def test_concurrent_aaa_and_daily_owner_has_single_authorized_writer(self):
        h=self.helper
        def write(kind):
            try:
                require_ownership(self.scope,self.grant,kind)
                if kind=='AAA_METADATA':h.consume()
                else:
                    with h.uow.transaction(self.scope):
                        locked_owner(h.db.state['subscribers'][0],self.scope,operation_id=None,writer='DAILY_OWNER')
                return 'WIN'
            except (OwnerContractConflict,MetadataConflict):return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(write,('AAA_METADATA','DAILY_OWNER'))),['WIN','CONFLICT'])
        self.assertEqual(len(h.db.state['events']),1);self.assertEqual(len(h.db.state['outbox']),1)

    def test_atomic_consume_rollback_and_replay_under_common_contract(self):
        h=self.helper;before=deepcopy(h.db.state);h.db.fail='events'
        with self.assertRaises(RuntimeError):h.consume()
        self.assertEqual(before,h.db.state)
        h.db.fail=None;h.consume();before=deepcopy(h.db.state)
        with self.assertRaises((OwnerContractConflict,MetadataConflict)):h.consume()
        self.assertEqual(before,h.db.state)

    def test_old_boolean_authorizer_and_missing_owner_block_issue(self):
        h=self.helper
        uow=PostgresMetadataUow(h.db.session,lambda s:True,lambda s,c:True,lambda *a:True)
        with self.assertRaises(PermissionError):
            with uow.transaction(self.scope) as repo:repo.reserve(h.request,h.op)
        del h.db.state['subscribers'][0]['aaa_fence']
        before=deepcopy(h.db.state)
        with self.assertRaises(OwnerContractConflict):
            with h.uow.transaction(self.scope) as repo:repo.issue(h.request.request_id,h.action)
        self.assertEqual(before,h.db.state)

    def test_shared_metadata_transition_must_advance_revision_and_fence(self):
        h=self.helper
        require_metadata_transition(h.old,h.new,operation_id=h.request.request_id)
        for change in ({'revision':h.old.revision},{'fence':h.old.fence},{'authority':'RADIUS'},{'active_request':None}):
            with self.assertRaises(OwnerContractConflict):
                require_metadata_transition(h.old,h.new.model_copy(update=change),operation_id=h.request.request_id)
        before=h.old.model_copy(update={'active_request':None})
        after=h.new.model_copy(update={'active_request':None})
        require_metadata_transition(before,after,operation_id=None,writer='DAILY_OWNER')
