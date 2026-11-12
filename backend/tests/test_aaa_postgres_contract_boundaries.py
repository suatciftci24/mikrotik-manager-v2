"""Offline PG dialect/DI boundary checks; never claim PostgreSQL runtime acceptance."""
from copy import deepcopy
from datetime import timedelta
from unittest import TestCase
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import dialect
from backend.tests import test_aaa_metadata_repository as fixtures
from app.repositories.aaa_metadata import MetadataConflict, owner
from app.repositories.aaa_owner_contract import OwnershipGrant, owner_cas_predicates, require_ownership


class PostgresContractBoundaryTests(TestCase):
    def setUp(self):
        self.h = fixtures.MetadataRepositoryTests(methodName='runTest')
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)

    def test_issue_rejects_subsecond_ttl_without_metadata_changes(self):
        h = self.h
        for seconds in (0.5, 0, -1, 300.5):
            with self.subTest(seconds=seconds):
                action = h.action.model_copy(update={'action_id': UUID(int=900),
                    'expires_at': h.now + timedelta(seconds=seconds)})
                before = deepcopy(h.db.state)
                with self.assertRaisesRegex(MetadataConflict, 'INVALID_AUTHORIZATION_TTL'):
                    with h.uow.transaction(h.scope) as repo:
                        repo.issue(h.request.request_id, action)
                self.assertEqual(h.db.state, before)

    def test_issue_revalidates_tampered_naive_timestamp_and_accepts_ttl_boundaries(self):
        h = self.h
        action = h.action.model_copy(update={'issued_at': h.now.replace(tzinfo=None)})
        before = deepcopy(h.db.state)
        with self.assertRaises(ValidationError):
            with h.uow.transaction(h.scope) as repo:
                repo.issue(h.request.request_id, action)
        self.assertEqual(h.db.state, before)
        for seconds in (1, 300):
            with h.uow.transaction(h.scope) as repo:
                repo.issue(h.request.request_id, h.action.model_copy(update={
                    'action_id': UUID(int=900 + seconds), 'expires_at': h.now + timedelta(seconds=seconds)}))
        self.assertEqual(len(h.db.state['actions']), 3)

    def test_membership_grant_cannot_use_truthy_active_or_noninteger_revision(self):
        h = self.h
        grant = OwnershipGrant(**h.scope.model_dump(), actor_active=True,
            membership_revision=1, capabilities=('AAA_METADATA',))
        for changes in ({'actor_active': 'false'}, {'actor_active': 1},
                        {'membership_revision': True}, {'membership_revision': 1.5}):
            with self.subTest(changes=changes):
                with self.assertRaises(PermissionError):
                    require_ownership(h.scope, grant.model_copy(update=changes))
        require_ownership(h.scope, grant)

    def test_postgresql_owner_cas_binds_scope_source_epoch_and_active_operation(self):
        h = self.h
        for writer in ('AAA_METADATA', 'DAILY_OWNER'):
            expected = h.old if writer == 'AAA_METADATA' else h.old.model_copy(update={'active_request': None})
            operation = h.request.request_id if writer == 'AAA_METADATA' else None
            predicates = owner_cas_predicates(owner, h.scope, expected, operation_id=operation, writer=writer)
            compiled = update(owner).where(*predicates).values(revision=4, aaa_fence=6).compile(dialect=dialect())
            sql = str(compiled)
            for column in ('tenant_id', 'id', 'revision', 'aaa_fence', 'source', 'aaa_active_operation'):
                self.assertIn('subscribers.' + column, sql)
            for value in (h.scope.tenant_id, h.scope.subscriber_id, h.old.revision, h.old.fence, 'LOCAL'):
                self.assertIn(value, compiled.params.values())
            if operation:
                self.assertIn(operation, compiled.params.values())
                self.assertIn('::UUID', sql)
            else:
                self.assertIn('aaa_active_operation IS NULL', sql)
