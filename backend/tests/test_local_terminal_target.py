"""Exercise the Bash terminal guard with simulated identities and no service IO."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]
OFFICE = '/home/suatpc/v26-transfer/mikrotik-v26-next'
HOME = '/home/suat/Codex-Projects/mikrotik-manager-v2'


class LocalTerminalTargetTests(TestCase):
    def setUp(self):
        self.temp = Path(self.enterContext(TemporaryDirectory()))
        env = {
            'PATH': f'{self.temp}:/usr/bin:/bin',
            'TEST_HOST': 'DESKTOP-VD5T7VG',
            'TEST_OS': 'Linux',
            'TEST_KERNEL': '6.18-microsoft-standard-WSL2',
            'TEST_USER': 'suatpc',
            'TEST_GIT_ROOT': OFFICE,
            'TEST_BRANCH': 'development/v2.6.2-pppoe',
            'TEST_ORIGIN': 'https://github.com/suatciftci24/mikrotik-manager-v2.git',
        }
        self.env = env
        for name, code in {
            'hostname': 'printf "%s\\n" "$TEST_HOST"',
            'uname': 'case "$1" in -s) echo "$TEST_OS";; -r) echo "$TEST_KERNEL";; esac',
            'id': 'echo "$TEST_USER"',
            'git': 'case "$3" in rev-parse) echo "$TEST_GIT_ROOT";; symbolic-ref) echo "$TEST_BRANCH";; config) echo "$TEST_ORIGIN";; esac',
        }.items():
            executable = self.temp / name
            executable.write_text(f'#!/bin/sh\n{code}\n')
            executable.chmod(0o700)

    def run_guard(self, root=OFFICE, **overrides):
        return subprocess.run(['/bin/bash', '-euc', 'source "$1"; require_local_terminal_target "$2"',
                               'guard', str(ROOT / 'tools/local-terminal-target.sh'), root],
                              env={**self.env, **overrides}, capture_output=True, text=True, timeout=5)

    def test_office_and_documented_home_workflows_pass(self):
        results = [
            self.run_guard(),
            self.run_guard(HOME, TEST_HOST='DESKTOP-MT2JS7H', TEST_USER='suat',
                           TEST_GIT_ROOT=HOME, TEST_BRANCH='main-guncel',
                           TEST_ORIGIN='git@github.com:suatciftci24/mikrotik-manager-v2.git'),
        ]
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_terminal_user_checkout_branch_or_origin_is_blocked(self):
        for root, overrides in [
            (OFFICE, {'TEST_HOST': 'vds-server', 'TEST_KERNEL': '6.8-generic'}),
            (OFFICE, {'TEST_OS': 'RouterOS'}),
            (OFFICE, {'TEST_OS': 'MINGW64_NT'}),
            (OFFICE, {'TEST_HOST': 'OTHER-WSL'}),
            (OFFICE, {'TEST_USER': 'root'}),
            (HOME, {}),
            (OFFICE, {'TEST_GIT_ROOT': HOME}),
            (OFFICE, {'TEST_BRANCH': 'main-guncel'}),
            (OFFICE, {'TEST_BRANCH': ''}),
            (OFFICE, {'TEST_ORIGIN': 'https://github.com/example/old-panel'}),
        ]:
            with self.subTest(root=root, overrides=overrides):
                result = self.run_guard(root, **overrides)
                self.assertEqual(result.returncode, 1)
                self.assertIn('TERMINAL_TARGET_BLOCKED', result.stderr)

    def test_entrypoints_block_before_bootstrap_and_keep_central_informational(self):
        (self.temp / 'tools').mkdir()
        shutil.copyfile(ROOT / 'tools/local-terminal-target.sh', self.temp / 'tools/local-terminal-target.sh')
        for script, argv in [('dev.sh', ['--ui-only']), ('dev.sh', ['--accept-demo']),
                             ('dev-db.sh', []), ('repair-demo.sh', []),
                             ('browser-accept-demo.sh', []), ('accept-demo.sh', [])]:
            with self.subTest(script=script, argv=argv):
                shutil.copyfile(ROOT / script, self.temp / script)
                result = subprocess.run(['/bin/bash', script, *argv], cwd=self.temp, env=self.env,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertIn('TERMINAL_TARGET_BLOCKED', result.stderr)
        result = subprocess.run(['/bin/bash', 'dev.sh', '--central'], cwd=self.temp, env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('https://v26.mikmanager.com.tr/', result.stdout)
        self.assertFalse((self.temp / '.venv').exists())
        self.assertFalse((self.temp / '.local').exists())
