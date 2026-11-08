"""Socketless policy checks for the manual synthetic Chromium runner."""
import json
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
        helper = (runner.REPO / 'frontend/tests/v26AcceptanceProfile.mjs').read_text()
        runner_source = (runner.REPO / 'backend/tests/run_v26_chromium_acceptance_wsl.py').read_text()
        self.assertNotIn("runtime_profile:'v26-isolated-acceptance'", source)
        self.assertIn("readyUrl=V26_HTTP_API_BASE+'/api/ready'", source)
        self.assertIn('maxRedirects:0,maxRetries:0', source)
        self.assertIn("requireV26AcceptanceReadiness(response.status(),await response.json())", source)
        self.assertIn("payload.runtime_profile!=='v26-isolated-acceptance'", helper)
        self.assertIn('http_runner.preflight()', runner_source)
        self.assertIn('result = http_runner.main(', runner_source)
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

    def test_browser_diagnostic_skips_broad_suites_and_classifies_only_safe_error_fields(self):
        source = (runner.REPO / 'backend/tests/run_v26_chromium_acceptance_wsl.py').read_text()
        browser = (runner.REPO / 'frontend/tests/managementCenters.browser.mjs').read_text()
        self.assertIn("parser.add_argument('--browser-only-diagnostic'", source)
        self.assertIn('if not args.browser_only_diagnostic:', source)
        self.assertIn('browser_only=args.browser_only_diagnostic', source)
        self.assertIn("phase='STATIC_HTTP_BIND'", browser)
        self.assertIn("phase='CHROMIUM_LAUNCH'", browser)
        self.assertIn('error_class=${safeName}', browser)
        self.assertIn('errno=${safeErrno}', browser)
        self.assertIn("replace(/https?:\\/\\/[^\\s)]+/gi,'[url]')", browser)
        self.assertIn('.slice(0,180)', browser)
        self.assertIn("page.locator('.workspace-context strong').first().waitFor()", browser)
        self.assertNotIn("getByText('V2.6 İzole Kabul Ortamı',{exact:false})", browser)
        self.assertNotIn('detail=${error.message}', browser)
        self.assertNotIn('${error.stack}', browser)
        self.assertIn("reportError('BROWSER_CLEANUP',error)", browser)
        self.assertIn("reportError('STATIC_HTTP_CLEANUP',error)", browser)
        self.assertIn("reportError('TEMP_CLEANUP',error)", browser)
        self.assertIn("PASS: browser scenario and owned resources cleanup complete", browser)
        self.assertIn('let browser,base,server;', browser)
        self.assertIn('server=createServer(', browser)
        self.assertNotIn('const server=createServer(', browser)

    def test_playwright_dependency_is_exact_and_lockfile_matches(self):
        frontend = runner.REPO / 'frontend'
        manifest = json.loads((frontend / 'package.json').read_text())
        lock = json.loads((frontend / 'package-lock.json').read_text())
        self.assertEqual(manifest['devDependencies']['playwright-core'], '1.64.1')
        self.assertEqual(lock['packages']['']['devDependencies']['playwright-core'], '1.64.1')
        self.assertEqual(lock['packages']['node_modules/playwright-core']['version'], '1.64.1')
        self.assertEqual(
            lock['packages']['node_modules/playwright-core']['integrity'],
            'sha512-BC4s8y6SEVA6Q1rSxZTto8hI1KUI3xXlHGZgvGqP4IqPdI/a6FX9H29IDNz7vKo9l21b6LfYosScPL6M3xxyDQ==',
        )


if __name__ == '__main__':
    import unittest
    unittest.main()
