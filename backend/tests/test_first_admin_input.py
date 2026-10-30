"""First ADMIN input regression tests. Synthetic secrets only, no DB/account or network IO."""
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import select
import signal
import sys
import time
from types import SimpleNamespace
from unittest import TestCase, SkipTest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app import first_admin as cli
from app.services.first_admin import FirstAdminIdentity, FirstAdminInput

PUBLIC = ['fixtureoperator', 'Fixture Operator', 'fixture.admin@example.test']
SECRET = '  SYNTHETIC-parola-çğı-91  '
ROOT = Path(__file__).resolve().parents[2]


class FirstAdminInputTests(TestCase):
    def run_cli(self, public, passwords, confirm=None):
        output = io.StringIO()
        store = Mock()
        store.status.return_value = SimpleNamespace(closed=False)
        with patch.object(cli, 'local_owner', return_value=os.getuid()), patch.object(cli, 'require_tty'), patch.object(cli, 'FirstAdminStore', return_value=store), patch('app.core.database.engine', Mock()), patch('builtins.input', side_effect=[*public, *([] if confirm is None else [confirm])]), patch.object(cli.getpass, 'getpass', side_effect=passwords) as hidden, redirect_stdout(output), redirect_stderr(output):
            status = cli.main(['--create'])
        store.create.assert_not_called()
        return status, output.getvalue(), hidden.call_count

    def test_valid_public_identity_and_exact_unicode_secret_survive_all_handoffs(self):
        with patch('builtins.input', side_effect=['  ' + value + '  ' for value in PUBLIC]), patch.object(cli.getpass, 'getpass', side_effect=[SECRET, SECRET]), patch.object(cli.hmac, 'compare_digest', wraps=cli.hmac.compare_digest) as compare:
            payload = cli.collect_input()
        self.assertEqual(list(payload.model_dump().values()), PUBLIC)
        self.assertEqual(payload.password.get_secret_value(), SECRET)
        rechecked = FirstAdminInput.model_validate({**payload.model_dump(), 'password': payload.password})
        self.assertEqual(rechecked.password.get_secret_value(), SECRET)
        compare.assert_called_once_with(SECRET.encode('utf-8'), SECRET.encode('utf-8'))
        self.assertNotIn(SECRET, repr(payload))
        self.assertNotIn('password', payload.model_dump())

    def test_public_field_errors_are_specific_without_prompting_for_a_password(self):
        for index, bad, label in [(0, 'bad/name', 'Giriş adı'), (0, 'demo', 'Giriş adı'),
                                  (1, '   ', 'Ad soyad'), (1, 'control\tname', 'Ad soyad'),
                                  (2, 'not-an-email', 'E-posta')]:
            with self.subTest(field=index):
                values = PUBLIC.copy()
                values[index] = bad
                status, output, prompts = self.run_cli(values, [])
                self.assertEqual(status, 1)
                self.assertEqual(prompts, 0)
                self.assertIn('ACCOUNT_INPUT_INVALID; ' + label + ':', output)
                self.assertNotIn(bad, output)
                for value in PUBLIC:
                    self.assertNotIn(value, output)

    def test_password_rejection_names_the_policy_without_echoing_value_or_actual_length(self):
        for password, reason in [('x' * 13, 'En az 14'), ('x' * 129, 'En çok 128'),
                                 (' ' * 20, 'Yalnız boşluk'), ('synthetic-test-\n-password', 'Satır sonu veya NUL'),
                                 ('synthetic-test-\0-password', 'Satır sonu veya NUL'),
                                 ('synthetic-test-\ud800-password', 'Geçerli UTF-8')]:
            with self.subTest(policy=reason):
                status, output, prompts = self.run_cli(PUBLIC, [password])
                self.assertEqual(status, 1)
                self.assertEqual(prompts, 1)
                self.assertIn('ACCOUNT_INPUT_INVALID; Parola: ' + reason, output)
                self.assertNotIn(password, output)
                self.assertNotIn('input_value', output)
                self.assertNotIn('Traceback', output)

    def test_password_policy_boundaries_remain_unchanged(self):
        public = dict(zip(('username', 'name', 'email'), PUBLIC))
        for length in (14, 128):
            payload = FirstAdminInput(**public, password='x' * length)
            self.assertEqual(len(payload.password.get_secret_value()), length)
        for length in (13, 129):
            with self.assertRaises(ValidationError):
                FirstAdminInput(**public, password='x' * length)

    def test_mismatch_and_unicode_normalization_difference_stop_without_a_write(self):
        for repeated in (SECRET.strip(), SECRET.replace('ç', 'c\u0327')):
            status, output, prompts = self.run_cli(PUBLIC, [SECRET, repeated])
            self.assertEqual(status, 1)
            self.assertEqual(prompts, 2)
            self.assertIn('PASSWORD_CONFIRMATION_MISMATCH', output)
            self.assertNotIn(SECRET, output)
            self.assertNotIn(repeated, output)

    def test_invalid_confirmation_encoding_names_repeat_field_without_echo(self):
        repeated = 'SYNTHETIC-invalid-repeat-\ud800'
        status, output, prompts = self.run_cli(PUBLIC, [SECRET, repeated])
        self.assertEqual(status, 1)
        self.assertEqual(prompts, 2)
        self.assertIn('PASSWORD_CONFIRMATION_INVALID', output)
        self.assertNotIn('LOCAL_SETUP_NOT_COMPLETED', output)
        self.assertNotIn(SECRET, output)
        self.assertNotIn(repeated, output)

    def test_hidden_tty_failure_is_distinct_from_account_validation(self):
        status, output, prompts = self.run_cli(PUBLIC, [cli.getpass.GetPassWarning(SECRET)])
        self.assertEqual(status, 1)
        self.assertEqual(prompts, 1)
        self.assertIn('HIDDEN_TTY_REQUIRED', output)
        self.assertNotIn('ACCOUNT_INPUT_INVALID', output)
        self.assertNotIn(SECRET, output)

    def test_validation_diagnostics_ignore_raw_message_context_and_unknown_field_names(self):
        sentinel = 'SYNTHETIC_PRIVATE_INPUT_CANARY'
        failure = ValidationError.from_exception_data('Fixture', [
            {'type': 'value_error', 'loc': ('password',), 'input': sentinel, 'ctx': {'error': ValueError(sentinel)}},
            {'type': 'extra_forbidden', 'loc': (sentinel,), 'input': sentinel},
        ])
        message = cli.validation_message(failure)
        self.assertIn('Parola:', message)
        self.assertIn('Kurulum alanları:', message)
        self.assertNotIn(sentinel, message)
        with self.assertRaises(ValidationError) as caught:
            FirstAdminInput(**dict(zip(('username', 'name', 'email'), PUBLIC)), password=sentinel + '\n')
        self.assertNotIn(sentinel, str(caught.exception))

    def test_controls_in_public_fields_still_fail_instead_of_being_silently_trimmed(self):
        for value in ('\tfixtureoperator', 'fixtureoperator\n', 'fixture\0operator'):
            with self.assertRaises(ValidationError):
                FirstAdminIdentity(username=value, name=PUBLIC[1], email=PUBLIC[2])

    def test_cancel_after_valid_hidden_input_does_not_create_account(self):
        status, output, prompts = self.run_cli(PUBLIC, [SECRET, SECRET], confirm='IPTAL')
        self.assertEqual(status, 1)
        self.assertEqual(prompts, 2)
        self.assertIn('SETUP_CANCELLED', output)
        self.assertNotIn(SECRET, output)

    def test_real_synthetic_tty_has_hidden_password_and_preserves_field_mapping(self):
        import pty
        source = '''
from unittest.mock import patch
from app.first_admin import require_tty, collect_input
from app.services.first_admin import FirstAdminInput
with patch('socket.socket', side_effect=AssertionError('No network IO')):
    require_tty()
    value = collect_input()
    check = FirstAdminInput.model_validate({**value.model_dump(), 'password': value.password})
    assert (check.username, check.name, check.email) == ('fixtureoperator', 'Fixture Operator', 'fixture.admin@example.test')
    assert check.password.get_secret_value() == '  SYNTHETIC-parola-çğı-91  '
    print('SYNTHETIC_TTY_PASS', flush=True)
'''
        try:
            pid, descriptor = pty.fork()
        except OSError:
            raise SkipTest('BLOCKED: synthetic local TTY unavailable') from None
        if pid == 0:
            environment = {**os.environ, 'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONUTF8': '1'}
            os.execve(sys.executable, [sys.executable, '-u', '-c', source], environment)
        output = bytearray()
        stopped = False
        deadline = time.monotonic() + 10

        def wait_for(prompt):
            expected = prompt.encode('utf-8')
            while expected not in output:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([descriptor], [], [], remaining)[0]:
                    self.fail('Synthetic TTY input did not complete within the bound')
                try:
                    chunk = os.read(descriptor, 4096)
                except OSError:
                    self.fail('Synthetic TTY process ended before expected prompt')
                if not chunk:
                    self.fail('Synthetic TTY process exited early')
                output.extend(chunk)

        try:
            for prompt, value in [('Yeni V2 ADMIN giriş adı: ', PUBLIC[0]), ('Ad soyad: ', PUBLIC[1]),
                                  ('E-posta: ', PUBLIC[2]), ('Yeni parola (14–128 karakter, gizli): ', SECRET),
                                  ('Parola tekrar (gizli): ', SECRET)]:
                wait_for(prompt)
                os.write(descriptor, value.encode('utf-8') + b'\n')
            wait_for('SYNTHETIC_TTY_PASS')
            _, status = os.waitpid(pid, 0)
            stopped = True
            self.assertEqual(os.waitstatus_to_exitcode(status), 0)
            self.assertNotIn(SECRET.encode('utf-8'), bytes(output))
        finally:
            if not stopped:
                os.kill(pid, signal.SIGTERM)
                os.waitpid(pid, 0)
            os.close(descriptor)
