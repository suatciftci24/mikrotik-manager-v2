import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('fresh_ssh', str(ROOT/'mikrotik-v2-fresh-ssh'))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class AccessTests(unittest.TestCase):
    def test_exact_sudo_and_ssh_scope(self):
        policy = (ROOT/'mikrotik-v2-fresh-ops.sudoers').read_text()
        grants = policy.split('NOPASSWD: ', 1)[1].strip().split(', ')
        expected = []
        for action in module.ACTIONS:
            for unit in module.UNITS:
                argv = module.command(f'{action} {unit}')
                self.assertEqual(argv[:3], ['/usr/bin/sudo', '-n', '--'])
                expected.append(' '.join(argv[3:]))
        self.assertCountEqual(grants, expected)

    def test_reject_escape_and_legacy(self):
        for original in ('', 'sh', 'sudo -i', 'start ssh.service',
                         'restart mikrotik-v2-cebeci-pilot.service',
                         'restart mikrotik-v2-fresh-pilot.service; id',
                         'restart mikrotik-v2-fresh-pilot.service --no-block',
                         'cat /srv/mikrotik-manager-v2-fresh-pilot/config/database.env',
                         'scp -t /tmp/x', 'internal-sftp',
                         ' start mikrotik-v2-fresh-pilot.service'):
            self.assertIsNone(module.command(original))

    def test_forced_command_default_denies_without_sudo(self):
        result = subprocess.run(['/usr/bin/python3', '-I', str(ROOT/'mikrotik-v2-fresh-ssh')],
                                env={}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr.strip(), 'BLOCKED: COMMAND_NOT_ALLOWED')

    def test_ssh_restrictions(self):
        config = (ROOT/'sshd-match.conf').read_text()
        for value in ('ForceCommand /usr/local/sbin/mikrotik-v2-fresh-ssh',
                      'DisableForwarding yes', 'PermitTTY no',
                      'PermitUserRC no',
                      'AuthenticationMethods publickey'):
            self.assertIn(value, config)
        self.assertFalse(any(line.strip().lower().startswith('permituserenvironment ')
                             for line in config.splitlines()))


class EnvironmentGateTests(unittest.TestCase):
    def test_effective_global_environment_gate(self):
        loader = importlib.machinery.SourceFileLoader('access_apply', str(ROOT/'apply-approved-vds.py'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        access = importlib.util.module_from_spec(spec)
        loader.exec_module(access)
        access.require_environment_disabled('permituserenvironment no\n')
        for settings in ('', 'permituserenvironment yes\n', 'permituserenvironment LANG,LC_*\n'):
            with self.assertRaisesRegex(RuntimeError, 'GLOBAL_USER_ENVIRONMENT_NOT_DISABLED'):
                access.require_environment_disabled(settings)


if __name__ == '__main__':
    unittest.main()
