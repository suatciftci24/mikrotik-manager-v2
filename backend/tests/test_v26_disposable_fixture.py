"""No PostgreSQL process, socket or existing acceptance directory is touched."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from backend.tests.v26_disposable_cluster import DisposableClusterGuard


class DisposableFixtureTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='v26-fixture-guard-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / 'postgres-test'
        self.data.mkdir(mode=0o700)
        (self.data / 'PG_VERSION').write_text('16\n')
        self.guard = DisposableClusterGuard(self.root)

    def test_accepts_only_captured_private_cluster_and_rejects_vds_or_another_path(self):
        self.guard(str(self.data))
        for value in ('/var/lib/postgresql/16/v26', str(self.root),
                      str(self.root / 'other'), 'postgres-test'):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.guard(value)

    def test_replaced_directory_cannot_impersonate_initialized_cluster(self):
        self.data.rename(self.root / 'previous')
        self.data.mkdir(mode=0o700)
        (self.data / 'PG_VERSION').write_text('16\n')
        with self.assertRaisesRegex(RuntimeError, 'IDENTITY_REJECTED'):
            self.guard(self.data)

    def test_symlink_or_insecure_permissions_fail_closed(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.data, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.guard(alias)
        self.data.rename(self.root / 'real-data')
        self.data.symlink_to(self.root / 'real-data', target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.guard(self.data)
        self.data.unlink()
        (self.root / 'real-data').rename(self.data)
        for path in (self.root, self.data):
            path.chmod(0o750)
            try:
                with self.assertRaises(RuntimeError):
                    self.guard(self.data)
            finally:
                path.chmod(0o700)

    def test_owner_and_version_change_or_missing_data_are_rejected(self):
        with patch('backend.tests.v26_disposable_cluster.os.geteuid', return_value=0):
            with self.assertRaises(RuntimeError):
                self.guard(self.data)
        info = self.data.stat()
        wrong = os.stat_result((info.st_mode, info.st_ino, info.st_dev,
                                info.st_nlink, info.st_uid + 1, info.st_gid,
                                info.st_size, info.st_atime, info.st_mtime, info.st_ctime))
        original = Path.lstat
        with patch.object(Path, 'lstat', autospec=True,
                          side_effect=lambda path: wrong if path == self.data else original(path)):
            with self.assertRaises(RuntimeError):
                self.guard(self.data)
        (self.data / 'PG_VERSION').write_text('15\n')
        with self.assertRaises(RuntimeError):
            self.guard(self.data)
        (self.data / 'PG_VERSION').unlink()
        with self.assertRaises(OSError):
            self.guard(self.data)

    def test_substitute_does_not_escape_patch_scope(self):
        from app.services import v26_identity
        original = v26_identity.verify_cluster
        with patch.object(v26_identity, 'verify_cluster', side_effect=self.guard):
            v26_identity.verify_cluster(str(self.data))
        self.assertIs(v26_identity.verify_cluster, original)

    def test_store_keeps_database_identity_and_marker_checks_with_substitute(self):
        from app.services import v26_identity
        from app.services.first_admin import SetupBlocked
        store = object.__new__(v26_identity.V26FirstAdminStore)
        store.store = Mock()
        connection = Mock()
        connection.execute.return_value.one.return_value = (
            'mikrotik_v26_acceptance', 'v26_acceptance', 55433)
        connection.execute.return_value.scalar_one.return_value = str(self.data)
        with patch.object(v26_identity, 'owner') as owner, \
             patch.object(v26_identity, 'verify_cluster', side_effect=self.guard):
            store._check(connection)
            owner.assert_called_once_with()
            store.store._verify.assert_called_once_with(connection)
            store.store._verify.reset_mock()
            connection.execute.return_value.one.return_value = (
                'mikrotik_manager_v2', 'v26_acceptance', 55433)
            with self.assertRaises(SetupBlocked):
                store._check(connection)
            store.store._verify.assert_not_called()
            connection.execute.return_value.one.return_value = (
                'mikrotik_v26_acceptance', 'v26_acceptance', 55433)
            connection.execute.return_value.scalar_one.return_value = '/var/lib/postgresql/16/v26'
            with self.assertRaises(RuntimeError):
                store._check(connection)
            store.store._verify.assert_not_called()
