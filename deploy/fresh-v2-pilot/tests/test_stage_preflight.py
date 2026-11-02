"""Offline staging regressions; no DB, sockets, host mutations or dependencies."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import manage

spec = importlib.util.spec_from_file_location('stage_preflight', HERE/'stage-approved.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class SourcePreflight(unittest.TestCase):
    def fixture(self, root):
        for name in stage.SOURCE_AREAS:
            (root/name).mkdir(parents=True)
        (root/'frontend/dist').mkdir()
        (root/'frontend/dist/index.html').write_text('synthetic')

    def test_complete_source_and_excluded_local_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root/'backend/.local').symlink_to('/nonexistent-synthetic')
            with patch.object(manage, 'REPO', root):
                stage.source_preflight()

    def test_missing_build_symlink_and_fifo_rejected(self):
        for kind in ('missing-build', 'root-symlink', 'nested-symlink', 'fifo'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root)
                if kind == 'missing-build':
                    (root/'frontend/dist/index.html').unlink()
                elif kind == 'root-symlink':
                    (root/'backend').rmdir()
                    (root/'backend').symlink_to(root/'migrations')
                elif kind == 'nested-symlink':
                    (root/'frontend/dist/escape').symlink_to('/nonexistent-synthetic')
                else:
                    os.mkfifo(root/'backend/pipe')
                with patch.object(manage, 'REPO', root), self.assertRaises(manage.Blocked):
                    stage.source_preflight()

    def test_source_failure_precedes_target_accounts_processes_and_sockets(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'absent-target'
            with patch.object(stage, 'ROOT', target), patch.object(manage, 'check_sources'), \
                 patch.object(stage.os, 'geteuid', return_value=0), \
                 patch.object(stage, 'source_preflight', side_effect=manage.Blocked('SOURCE_REJECTED')), \
                 patch.object(stage.pwd, 'getpwnam') as accounts, \
                 patch.object(stage, 'run') as process, patch.object(stage.socket, 'socket') as sockets:
                with self.assertRaisesRegex(manage.Blocked, 'SOURCE_REJECTED'):
                    stage.stage()
                self.assertFalse(target.exists())
                accounts.assert_not_called()
                process.assert_not_called()
                sockets.assert_not_called()


if __name__ == '__main__':
    unittest.main()
