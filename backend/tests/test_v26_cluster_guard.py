"""Network-free tests of the fixed VDS PGDATA boundary; no cluster is touched."""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from app.services.first_admin import SetupBlocked
from app.services.v26_identity import V26FirstAdminStore, verify_cluster


class ClusterGuardTests(TestCase):
    def check(self, value='/var/lib/postgresql/16/v26', *, uid=111, mode=0o40700,
              resolved=None, symlink=False, directory=True, failure=None):
        with patch.object(Path, 'resolve', return_value=Path(resolved or value)), \
             patch.object(Path, 'lstat', return_value=SimpleNamespace(st_uid=uid, st_mode=mode),
                          side_effect=failure), \
             patch.object(Path, 'is_dir', return_value=directory), \
             patch.object(Path, 'is_symlink', return_value=symlink), \
             patch('app.services.v26_identity.pwd.getpwnam', return_value=SimpleNamespace(pw_uid=111)):
            verify_cluster(value)

    def test_only_fixed_postgres_owned_private_cluster_is_accepted(self):
        self.check()
        for args in (dict(value='/tmp/mikrotik-v26-acceptance/postgres-test'),
                     dict(value='/var/lib/postgresql/16/main'),
                     dict(value='var/lib/postgresql/16/v26'), dict(uid=1000),
                     dict(mode=0o40750), dict(mode=0o40707), dict(symlink=True),
                     dict(resolved='/another/cluster'), dict(directory=False)):
            with self.subTest(args=args), self.assertRaisesRegex(SetupBlocked, '^V26_CLUSTER_REJECTED$'):
                self.check(**args)

    def test_inaccessible_missing_or_unresolvable_metadata_fails_safely(self):
        for failure in (PermissionError('private-detail'), FileNotFoundError('private-detail'),
                        KeyError('private-detail'), RuntimeError('private-detail')):
            with self.subTest(error=type(failure).__name__), \
                 self.assertRaisesRegex(SetupBlocked, '^V26_CLUSTER_METADATA_UNAVAILABLE$'):
                self.check(failure=failure)

    def test_wrong_database_or_cluster_never_verifies_marker(self):
        store = object.__new__(V26FirstAdminStore)
        store.store = Mock()
        connection = Mock()
        connection.execute.return_value.one.return_value = ('wrong', 'v26_acceptance', 55433)
        with patch('app.services.v26_identity.owner'), \
             self.assertRaisesRegex(SetupBlocked, 'V26_DATABASE_REJECTED'):
            store._check(connection)
        store.store._verify.assert_not_called()
        connection.execute.return_value.one.return_value = ('mikrotik_v26_acceptance', 'v26_acceptance', 55433)
        connection.execute.return_value.scalar_one.return_value = '/var/lib/postgresql/16/main'
        with patch('app.services.v26_identity.owner'), \
             self.assertRaisesRegex(SetupBlocked, 'V26_CLUSTER_REJECTED'):
            store._check(connection)
        store.store._verify.assert_not_called()
