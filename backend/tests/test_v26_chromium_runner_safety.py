"""Socketless policy checks for the manual synthetic Chromium runner."""
from pathlib import Path
from unittest import TestCase

from backend.tests import run_v26_chromium_acceptance_wsl as runner


class V26ChromiumRunnerSafety(TestCase):
    def context(self, **changes):
        values = dict(
            repo=runner.EXPECTED_REPO, cwd=runner.EXPECTED_REPO,
            hostname=runner.EXPECTED_HOST, wsl=True, uid=1000, owner_uid=1000,
            branch=runner.EXPECTED_BRANCH, clean=True, node_path='/usr/bin/node',
            playwright_exists=True, esbuild_exists=True,
        )
        values.update(changes)
        return runner.blocked_precondition(**values)

    def test_only_expected_clean_home_wsl_tree_and_local_toolchain_are_eligible(self):
        self.assertIsNone(self.context())
        self.assertEqual(self.context(repo=Path('/tmp/repo')), 'REPOSITORY_PATH_REJECTED')
        self.assertEqual(self.context(cwd=Path('/tmp')), 'REPOSITORY_PATH_REJECTED')
        self.assertEqual(self.context(hostname='office-wsl'), 'HOME_WSL_IDENTITY_REJECTED')
        self.assertEqual(self.context(wsl=False), 'HOME_WSL_IDENTITY_REJECTED')
        self.assertEqual(self.context(uid=0), 'REPOSITORY_OWNER_REJECTED')
        self.assertEqual(self.context(owner_uid=2000), 'REPOSITORY_OWNER_REJECTED')
        self.assertEqual(self.context(branch='other'), 'BRANCH_REJECTED')
        self.assertEqual(self.context(clean=False), 'DIRTY_WORKTREE_REJECTED')
        self.assertEqual(self.context(node_path=None), 'LOCAL_BROWSER_TOOLCHAIN_UNAVAILABLE')
        self.assertEqual(self.context(playwright_exists=False), 'LOCAL_BROWSER_TOOLCHAIN_UNAVAILABLE')
        self.assertEqual(self.context(esbuild_exists=False), 'LOCAL_BROWSER_TOOLCHAIN_UNAVAILABLE')

    def test_child_environment_drops_service_credentials_and_browser_overrides(self):
        safe = runner.safe_environment({
            'PATH': '/usr/bin:/bin', 'HOME': '/home/suat', 'LANG': 'C.UTF-8',
            'V2_DATABASE_URL': 'private-db', 'PGHOST': 'private-host',
            'V2_BROWSER_EXECUTABLE': '/private/browser', 'PLAYWRIGHT_BROWSERS_PATH': '/private/pw',
            'PYTHONPATH': '/injected', 'LD_PRELOAD': '/private/library',
        })
        self.assertEqual(safe, {'PATH': '/usr/bin:/bin', 'HOME': '/home/suat', 'LANG': 'C.UTF-8'})

    def test_browser_suite_contract_has_no_mutation_or_persistent_acceptance_artifacts(self):
        source = (runner.REPO / 'frontend/tests/managementCenters.browser.mjs').read_text()
        self.assertIn("runtime_profile:'v26-isolated-acceptance'", source)
        self.assertIn("request.method()!=='GET'", source)
        self.assertIn("server.listen(0,'127.0.0.1'", source)
        self.assertIn("join(tmpdir(),'v26-browser-acceptance-'", source)
        self.assertNotIn('screenshot(', source)
        self.assertNotIn('/api/v1/v1-inventory', source)
        self.assertNotIn("method:'POST'", source)
        self.assertNotIn("method:'DELETE'", source)
        self.assertNotIn('18996', source)
        self.assertNotIn('55433', source)
        self.assertIn("assert.ok(reads.includes('/api/ready')", source)


if __name__ == '__main__':
    import unittest
    unittest.main()
