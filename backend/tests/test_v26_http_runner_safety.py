"""Offline tests for the manual Home WSL acceptance entry point."""
from pathlib import Path
from unittest import TestCase

from backend.tests import run_v26_http_acceptance_wsl as runner


class HomeWslRunnerPolicyTests(TestCase):
    def context(self, **changes):
        values = dict(
            repo=runner.EXPECTED_REPO, cwd=runner.EXPECTED_REPO,
            hostname=runner.EXPECTED_HOST, wsl=True, uid=1000, owner_uid=1000,
            branch=runner.EXPECTED_BRANCH, clean=True,
            acceptance_root_exists=False, python_path=runner.EXPECTED_PYTHON,
        )
        values.update(changes)
        return runner.blocked_precondition(**values)

    def test_expected_manual_home_wsl_context_is_eligible(self):
        self.assertIsNone(self.context())

    def test_wrong_host_or_non_wsl_environment_is_blocked(self):
        self.assertEqual(self.context(hostname='office-wsl'), 'HOME_WSL_IDENTITY_REJECTED')
        self.assertEqual(self.context(wsl=False), 'HOME_WSL_IDENTITY_REJECTED')

    def test_wrong_path_owner_branch_or_dirty_tree_is_blocked(self):
        self.assertEqual(self.context(cwd=Path('/tmp')), 'REPOSITORY_PATH_REJECTED')
        self.assertEqual(self.context(uid=0), 'REPOSITORY_OWNER_REJECTED')
        self.assertEqual(self.context(branch='other'), 'BRANCH_REJECTED')
        self.assertEqual(self.context(clean=False), 'DIRTY_WORKTREE_REJECTED')

    def test_existing_acceptance_root_or_non_repo_python_is_blocked(self):
        self.assertEqual(self.context(acceptance_root_exists=True), 'ACCEPTANCE_ROOT_ALREADY_EXISTS')
        self.assertEqual(self.context(python_path=Path('/usr/bin/python3')), 'REPOSITORY_VENV_REQUIRED')

    def test_runtime_environment_drops_database_and_v2_overrides(self):
        safe = runner.runtime_environment({
            'PATH': '/usr/bin:/bin', 'HOME': '/home/suat', 'LANG': 'C.UTF-8',
            'PYTHONPATH': '/private/injected', 'PYTHONHOME': '/private/python',
            'V2_DATABASE_URL': 'private-target', 'PGHOST': 'private-host',
            'LD_PRELOAD': '/private/library', 'WSL_DISTRO_NAME': 'Ubuntu',
        })
        self.assertEqual(set(safe), {'PATH', 'HOME', 'LANG', 'PYTHONNOUSERSITE', 'PYTHONPATH'})
        self.assertNotIn('private', str(safe))
        self.assertEqual(safe['PYTHONPATH'],
                         f'{runner.REPO}:{runner.REPO / "backend"}:{runner.REPO / "backend/tests"}')


if __name__ == '__main__':
    import unittest
    unittest.main()
