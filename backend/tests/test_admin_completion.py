"""Filesystem/secret behavior of the one-shot operator helper; no DB/network."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[2] / 'deploy/cebeci-v2-pilot'
spec = importlib.util.spec_from_file_location('office_completion', PACKAGE / 'complete-office.py')
office = importlib.util.module_from_spec(spec)
spec.loader.exec_module(office)


class AdminCompletionSafetyTests(unittest.TestCase):
    def test_private_file_rejects_symlink_hardlink_and_public_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'secret'
            path.write_text('synthetic')
            path.chmod(0o600)
            office.private(path)
            link = Path(temp) / 'link'
            link.symlink_to(path)
            with self.assertRaises(RuntimeError):
                office.private(link)
            link.unlink()
            os.link(path, link)
            with self.assertRaises(RuntimeError):
                office.private(path)
            link.unlink()
            path.chmod(0o644)
            with self.assertRaises(RuntimeError):
                office.private(path)

    def test_export_passfile_is_private_no_password_argv_and_removed_on_failure(self):
        before = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.local').mkdir()
            os.chdir(root)
            url = 'postgresql+psycopg://v2_local:SYNTHETIC%3Apassword@127.0.0.1:55432/mikrotik_manager_v2'
            checked = []
            def failed_psql(args, env):
                checked.append(True)
                self.assertNotIn('SYNTHETIC', ' '.join(args))
                self.assertNotIn('PGPASSWORD', env)
                self.assertNotIn('PGSERVICE', env)
                path = Path(env['PGPASSFILE'])
                office.private(path)
                self.assertIn('SYNTHETIC\\:password', path.read_text())
                raise RuntimeError('synthetic failure')
            try:
                with patch.object(office, 'ROOT', root), patch.object(office, 'run', failed_psql), patch.dict(
                        os.environ, {'V2_DATABASE_URL': url, 'PGPASSWORD': 'ignored', 'PGSERVICE': 'ignored'}):
                    with self.assertRaises(RuntimeError):
                        office.export()
                self.assertEqual(checked, [True])
                self.assertEqual(list((root / '.local/admin-transfer').iterdir()), [])
            finally:
                os.chdir(before)

    def test_foreign_database_rejected_before_export(self):
        before = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.chdir(root)
            try:
                with patch.object(office, 'ROOT', root), patch.object(office, 'run') as command, patch.dict(
                        os.environ, {'V2_DATABASE_URL': 'postgresql+psycopg://v2_local:x@127.0.0.1:5432/v1'}):
                    with self.assertRaises(AssertionError):
                        office.export()
                    command.assert_not_called()
            finally:
                os.chdir(before)


if __name__ == '__main__':
    unittest.main()
