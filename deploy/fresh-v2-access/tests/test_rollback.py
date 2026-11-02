import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1]/'apply-approved-vds.py'


def load():
    spec = importlib.util.spec_from_file_location('access_rollback', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RollbackTests(unittest.TestCase):
    def test_failure_restores_config_disables_only_new_key_and_preserves_backup(self):
        module = load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module.CONFIG = root/'sshd_config'
            module.KEY = root/'v2-fresh-ops'
            backup = root/'old-backup'
            backup.write_text('previous evidence')
            module.CONFIG.write_text('original\nnew match\n')
            module.KEY.write_text('synthetic public key')
            module.CREATED_KEY = True
            module.ORIGINAL_CONFIG = 'original\n'
            module.INSTALLED_CONFIG = 'original\nnew match\n'
            module.run = Mock()
            module.fail_closed()
            self.assertEqual(module.CONFIG.read_text(), 'original\n')
            self.assertFalse(module.KEY.exists())
            self.assertTrue((root/'v2-fresh-ops.disabled').exists())
            self.assertEqual(backup.read_text(), 'previous evidence')
            module.run.assert_called_once_with(['/usr/sbin/sshd', '-t'])

    def test_concurrent_config_change_is_not_overwritten(self):
        module = load()
        with tempfile.TemporaryDirectory() as directory:
            module.CONFIG = Path(directory)/'sshd_config'
            module.CONFIG.write_text('other administrator change')
            module.ORIGINAL_CONFIG = 'original'
            module.INSTALLED_CONFIG = 'our candidate'
            with self.assertRaisesRegex(RuntimeError, 'CONFIG_CHANGED_CONCURRENTLY'):
                module.fail_closed()
            self.assertEqual(module.CONFIG.read_text(), 'other administrator change')

    def test_attempt_rollback_preserves_previous_disabled_key_and_policy(self):
        module = load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module.ATTEMPT_EVIDENCE = root/'new-evidence'
            module.ATTEMPT_EVIDENCE.mkdir()
            module.KEY = root/'v2-fresh-ops'
            module.KEY.write_text('new attempt key')
            old = root/'v2-fresh-ops.disabled'
            old.write_text('old evidence key')
            module.POLICY = root/'sudoers'
            module.POLICY.write_text('new attempt policy')
            module.CREATED_KEY = True
            module.CREATED_POLICY = True
            module.run = Mock()
            module.fail_closed()
            self.assertEqual(old.read_text(), 'old evidence key')
            self.assertEqual((module.ATTEMPT_EVIDENCE/'authorized_key.disabled').read_text(), 'new attempt key')
            self.assertEqual((module.ATTEMPT_EVIDENCE/'sudoers.disabled').read_text(), 'new attempt policy')
            self.assertFalse(module.KEY.exists())
            self.assertFalse(module.POLICY.exists())
