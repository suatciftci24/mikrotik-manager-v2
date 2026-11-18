"""Local transfer guard tests. Fixture Git accepts only read-only subcommands."""
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

TOOLS = Path(__file__).resolve().parent
HTTPS = 'https://github.com/suatciftci24/mikrotik-manager-v2.git'
SSH = 'git@github.com:suatciftci24/mikrotik-manager-v2.git'


class GitTransferTargetTests(TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.tools = self.root / 'tools'
        self.tools.mkdir()
        self.checker = self.tools / 'check-git-transfer.sh'
        shutil.copyfile(TOOLS / self.checker.name, self.checker)
        (self.tools / 'local-terminal-target.sh').write_text(
            (TOOLS / 'local-terminal-target.sh').read_text().replace(
                '/home/suatpc/v26-transfer/mikrotik-v26-next', str(self.root)))
        for name, code in {
            'hostname': 'echo DESKTOP-VD5T7VG',
            'uname': 'case "$1" in -s) echo Linux;; -r) echo microsoft-standard-WSL2;; esac',
            'id': 'echo suatpc',
            'git': '''case "$3:$4:$5" in
  rev-parse:--show-toplevel:) printf '%s\\n' "$FIXTURE_ROOT";;
  symbolic-ref:--quiet:--short) printf '%s\\n' "$FIXTURE_BRANCH";;
  config:--local:--get) printf '%s\\n' "$FIXTURE_RAW";;
  remote:get-url:--all) printf '%s\\n' "$FIXTURE_READ";;
  remote:get-url:--push) printf '%s\\n' "$FIXTURE_WRITE";;
  config:--bool:--get-all) [ -n "$FIXTURE_MIRROR" ] || exit 1; printf '%s\\n' "$FIXTURE_MIRROR";;
  *) exit 97;;
esac''',
        }.items():
            tool = self.root / name
            tool.write_text(f'#!/bin/sh\n{code}\n')
            tool.chmod(0o700)
        self.environment = {
            'PATH': f'{self.root}:/usr/bin:/bin', 'FIXTURE_ROOT': str(self.root),
            'FIXTURE_BRANCH': 'development/v2.6.2-pppoe', 'FIXTURE_RAW': HTTPS,
            'FIXTURE_READ': HTTPS, 'FIXTURE_WRITE': SSH, 'FIXTURE_MIRROR': '',
        }

    def check(self, *args, **env):
        return subprocess.run(['/bin/bash', str(self.checker), *args],
                              env={**self.environment, **env},
                              capture_output=True, text=True, timeout=5)

    def test_canonical_ssh_and_https_can_remain_configured(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('GIT_TRANSFER_TARGET_OK', result.stdout)

    def test_wrong_branch_multiple_or_rewritten_origin_and_mirror_are_rejected(self):
        secret = 'synthetic-secret'
        for env in (
            {'FIXTURE_BRANCH': 'main-guncel'},
            {'FIXTURE_RAW': f'https://{secret}@github.com/suatciftci24/mikrotik-manager-v2.git'},
            {'FIXTURE_READ': 'https://example.test/other.git'},
            {'FIXTURE_WRITE': f'https://{secret}@github.com/suatciftci24/mikrotik-manager-v2.git'},
            {'FIXTURE_WRITE': f'{HTTPS}\n{SSH}'},
            {'FIXTURE_MIRROR': 'true'},
        ):
            with self.subTest(key=list(env)):
                result = self.check(**env)
                self.assertEqual(result.returncode, 1)
                self.assertIn('_BLOCKED', result.stderr)
                self.assertNotIn(secret, result.stdout + result.stderr)

    def test_preflight_has_no_push_mode_and_historical_relay_requires_explicit_flag(self):
        self.assertEqual(self.check('--push').returncode, 1)
        relay = subprocess.run([sys.executable, '-B', str(TOOLS / 'v262-push-via-vds.py')],
                               capture_output=True, text=True, timeout=5)
        self.assertEqual(relay.returncode, 1)
        self.assertIn('--execute-pinned-relay', relay.stderr)
