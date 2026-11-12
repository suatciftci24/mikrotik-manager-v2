"""Provisioning guards only; never start PostgreSQL or open a real socket."""
from unittest import TestCase
from unittest.mock import patch, MagicMock
from backend.tests import run_aaa_postgres_wsl as runner


class AaaPostgresWslSafetyTests(TestCase):
    def test_foreign_host_denies_before_any_resource(self):
        with patch.object(runner.platform, 'node', return_value='foreign-host'), \
                patch.object(runner, 'OwnedRoot') as owned:
            with self.assertRaisesRegex(RuntimeError, 'HOME_WSL_IDENTITY_REJECTED'):
                runner.main()
            owned.assert_not_called()

    def test_existing_root_denies_before_socket_or_cluster(self):
        with patch.object(runner, 'home_guard'), \
                patch.object(runner.os.path, 'lexists', return_value=True), \
                patch.object(runner.socket, 'socket') as sock, \
                patch.object(runner, 'OwnedRoot') as owned:
            with self.assertRaisesRegex(RuntimeError, 'ACCEPTANCE_ROOT_ALREADY_EXISTS'):
                runner.main()
            sock.assert_not_called()
            owned.assert_not_called()

    def test_port_collision_denies_before_directory_creation(self):
        sock = MagicMock()
        sock.__enter__.return_value.bind.side_effect = OSError('synthetic collision')
        with patch.object(runner, 'home_guard'), \
                patch.object(runner.os.path, 'lexists', return_value=False), \
                patch.object(runner.socket, 'socket', return_value=sock), \
                patch.object(runner, 'OwnedRoot') as owned:
            with self.assertRaises(OSError):
                runner.main()
            sock.__enter__.return_value.bind.assert_called_once_with(('127.0.0.1', 55433))
            owned.assert_not_called()

    def test_acceptance_checks_cannot_be_removed_by_python_optimization(self):
        with self.assertRaisesRegex(RuntimeError, 'AAA_ACCEPTANCE_CHECK_FAILED'):
            runner.require(False)
        runner.require(True)

    def test_external_pg_options_are_removed_before_preparation(self):
        with patch.object(runner, 'home_guard'), \
                patch.dict(runner.os.environ, {'PGOPTIONS':'external', 'PGHOSTADDR':'external'}), \
                patch.object(runner, 'prepare') as prepare:
            def inspect():
                self.assertNotIn('PGOPTIONS', runner.os.environ)
                self.assertNotIn('PGHOSTADDR', runner.os.environ)
            prepare.side_effect = inspect
            runner.main()
            prepare.assert_called_once_with()
