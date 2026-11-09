"""Offline lifecycle tests: no socket, database, process signal or real acceptance."""
import io
import os
from pathlib import Path
import signal
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout
from tempfile import TemporaryDirectory

from backend.tests import v26_http_acceptance as harness
from backend.tests.v26_owned_resources import OwnedRoot


class CleanupLifecycleTests(unittest.TestCase):
    def run_main(self, action):
        events = []
        class Case(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                cls.addClassCleanup(events.append, 'class')
            def test_case(self):
                self.addCleanup(events.append, 'case')
                action()
        suite = unittest.TestSuite([Case('test_case')])
        output = io.StringIO()
        with patch.object(harness, 'preflight'), \
             patch.object(harness, 'acceptance_suite', return_value=suite), \
             redirect_stdout(output):
            code = harness.main(['--run'])
        return code, events, output.getvalue()

    def test_normal_and_assertion_failure_clean_once(self):
        for action, expected in ((lambda: None, 0),
                                 (lambda: self.fail('synthetic'), 1)):
            code, events, _ = self.run_main(action)
            self.assertEqual(code, expected)
            self.assertEqual(events, ['case', 'class'])

    def test_sigint_sigterm_restore_handlers_and_drain_class_cleanup(self):
        for number in (signal.SIGINT, signal.SIGTERM):
            before = signal.getsignal(number)
            code, events, output = self.run_main(
                lambda: signal.getsignal(number)(number, None))
            self.assertEqual(code, 1)
            self.assertEqual(events, ['case', 'class'])
            self.assertIn('ACCEPTANCE_INTERRUPTED', output)
            self.assertEqual(signal.getsignal(number), before)

    def test_interrupted_class_setup_is_cleaned(self):
        events = []
        class Case(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                cls.addClassCleanup(events.append, 'class')
                raise harness.AcceptanceInterrupted()
            def test_case(self):
                self.fail('must not run')
        with patch.object(harness, 'preflight'), \
             patch.object(harness, 'acceptance_suite', return_value=unittest.TestSuite([Case('test_case')])), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(harness.main(['--run']), 1)
        self.assertEqual(events, ['class'])

    def test_cleanup_failure_never_passes(self):
        def bad():
            raise RuntimeError('private details')
        class Case(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                cls.addClassCleanup(bad)
            def test_case(self):
                pass
        output = io.StringIO()
        with patch.object(harness, 'preflight'), \
             patch.object(harness, 'acceptance_suite', return_value=unittest.TestSuite([Case('test_case')])), \
             redirect_stdout(output):
            self.assertEqual(harness.main(['--run']), 1)
        self.assertNotIn('PASS:', output.getvalue())
        self.assertNotIn('private details', output.getvalue())


class OwnedResourceTests(unittest.TestCase):
    def owner(self):
        owner = object.__new__(OwnedRoot)
        owner.root = Path('/tmp/mikrotik-v26-acceptance')
        owner.parent_fd, owner.fd = 101, 102
        owner.data_identity = None
        owner.process_identity = None
        owner.start_after = 100
        owner.pg_stopped = False
        return owner

    def test_stop_pins_process_and_checks_identity_before_signal(self):
        owner = self.owner()
        identity = (1234, '500', ('pidfile',))
        with patch.object(owner, 'verify_data'), \
             patch('os.path.lexists', return_value=True), \
             patch.object(owner, 'process', return_value=identity) as process, \
             patch('os.pidfd_open', return_value=42) as pin, \
             patch('signal.pidfd_send_signal') as send, \
             patch('select.poll') as poll, patch('os.close'):
            poll.return_value.poll.return_value = [(42, 1)]
            owner.stop()
            self.assertEqual(process.call_count, 2)
            pin.assert_called_once_with(1234)
            send.assert_called_once_with(42, signal.SIGINT)
            self.assertTrue(owner.pg_stopped)

    def test_pid_reuse_or_tampered_process_never_signalled(self):
        owner = self.owner()
        for identities in (((1234, '500'), (1234, '501')),
                           (RuntimeError('OWN_PROCESS_OWNER_REJECTED'),)):
            with patch.object(owner, 'verify_data'), \
                 patch('os.path.lexists', return_value=True), \
                 patch.object(owner, 'process', side_effect=identities), \
                 patch('os.pidfd_open', return_value=42), \
                 patch('signal.pidfd_send_signal') as send, patch('os.close'):
                with self.assertRaises(RuntimeError):
                    owner.stop()
                send.assert_not_called()

    def test_stop_timeout_or_missing_pid_preserves_root(self):
        owner = self.owner()
        with patch.object(owner, 'verify_data'), patch('os.path.lexists', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'UNCONFIRMED'):
                owner.stop()
        with patch.object(owner, 'verify_data'), patch('os.path.lexists', return_value=True), \
             patch.object(owner, 'process', return_value=(1234, '500')), \
             patch('os.pidfd_open', return_value=42), patch('signal.pidfd_send_signal'), \
             patch('select.poll') as poll, patch('os.close'):
            poll.return_value.poll.return_value = []
            with self.assertRaisesRegex(RuntimeError, 'TIMEOUT'):
                owner.stop()
        self.assertFalse(owner.pg_stopped)

    def test_removal_rejects_identity_change_or_running_cluster(self):
        for changed in (True, False):
            owner = self.owner()
            with patch.object(owner, 'verify', side_effect=RuntimeError('identity') if changed else None), \
                 patch('shutil.rmtree') as remove, patch('os.close'):
                with self.assertRaises(RuntimeError):
                    owner.remove()
                remove.assert_not_called()

    def test_removal_uses_anchored_parent_and_closes_descriptors(self):
        owner = self.owner()
        owner.pg_stopped = True
        with patch.object(owner, 'verify'), patch('os.path.lexists', return_value=False), \
             patch('shutil.rmtree') as remove, patch('os.close') as close:
            owner.remove()
            remove.assert_called_once_with('mikrotik-v26-acceptance', dir_fd=101)
            self.assertEqual(close.call_count, 2)

    def test_existing_root_is_never_adopted_or_removed(self):
        with patch('os.open', return_value=101), \
             patch('os.mkdir', side_effect=FileExistsError), \
             patch('os.close'), patch('shutil.rmtree') as remove:
            with self.assertRaises(FileExistsError):
                OwnedRoot('/tmp/mikrotik-v26-acceptance')
            remove.assert_not_called()

    def test_real_directory_identity_symlink_permissions_and_replacement(self):
        # Ordinary fresh unit-test files only, never the fixed acceptance path.
        with TemporaryDirectory(prefix='v26-cleanup-unit-') as temporary:
            root = Path(temporary)
            owner = object.__new__(OwnedRoot)
            owner.root = root
            owner.parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY)
            owner.fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            owner.identity = owner._identity(os.fstat(owner.fd))
            try:
                owner.verify()
                root.chmod(0o750)
                with self.assertRaises(RuntimeError):
                    owner.verify()
                root.chmod(0o700)
                root.rename(root.with_name(root.name + '-old'))
                root.symlink_to(root.with_name(root.name + '-old'), target_is_directory=True)
                with self.assertRaises(RuntimeError):
                    owner.verify()
                root.unlink()
                root.with_name(root.name + '-old').rename(root)
            finally:
                os.close(owner.fd)
                os.close(owner.parent_fd)

    def test_process_checks_pidfile_owner_data_executable_and_start_identity(self):
        from backend.tests import v26_owned_resources as resources
        with TemporaryDirectory(prefix='v26-process-unit-') as temporary:
            root = Path(temporary)
            data = root / 'postgres-test'
            data.mkdir(mode=0o700)
            (data / 'PG_VERSION').write_text('16\n')
            proc_root = root / 'proc'
            proc = proc_root / '1234'
            proc.mkdir(parents=True)
            (proc / 'exe').symlink_to('/usr/lib/postgresql/16/bin/postgres')
            (proc / 'cwd').symlink_to(data, target_is_directory=True)
            (proc / 'cmdline').write_bytes(b'postgres\0-D\0' + os.fsencode(data) + b'\0')
            (proc / 'stat').write_text('1234 (postgres) ' + ' '.join(['S'] + ['0'] * 18 + ['500']))
            pidfile = data / 'postmaster.pid'
            valid = f'1234\n{data}\n100\n55433\n{root}/socket\n127.0.0.1\n'
            pidfile.write_text(valid)
            owner = self.owner()
            owner.root = root
            owner.data_identity = owner._identity(data.lstat())
            with patch.object(owner, 'verify'), patch.object(resources, 'PROC', proc_root):
                owner.capture_process()
                self.assertEqual(owner.process()[0], 1234)
                for bad in (valid.replace('55433', '5432'),
                            valid.replace(str(data), '/other/cluster'),
                            valid.replace('\n100\n', '\n99\n')):
                    pidfile.write_text(bad)
                    with self.assertRaises(RuntimeError):
                        owner.process()
                pidfile.write_text(valid)
                (proc / 'cmdline').write_bytes(b'postgres\0-D\0/other/cluster\0')
                with self.assertRaises(RuntimeError):
                    owner.process()
                (proc / 'cmdline').write_bytes(b'postgres\0-D\0' + os.fsencode(data) + b'\0')
                (proc / 'stat').write_text('1234 (postgres) ' + ' '.join(['S'] + ['0'] * 18 + ['501']))
                with self.assertRaisesRegex(RuntimeError, 'PROCESS_IDENTITY'):
                    owner.process()
                with patch.object(resources.os, 'getuid', return_value=os.getuid() + 1):
                    with self.assertRaises(RuntimeError):
                        owner.process()
                pidfile.unlink()
                (root / 'other-pid').write_text(valid)
                pidfile.symlink_to(root / 'other-pid')
                with self.assertRaisesRegex(RuntimeError, 'PID_FILE'):
                    owner.process()

    def test_data_directory_replacement_prevents_stop_and_remove(self):
        owner = self.owner()
        owner.data_identity = (1, 2, os.getuid())
        with patch.object(owner, 'verify'), patch.object(Path, 'lstat') as metadata, \
             patch.object(owner, '_identity', return_value=(1, 3, os.getuid())), \
             patch('signal.pidfd_send_signal') as send, patch('shutil.rmtree') as remove, \
             patch('os.close'):
            with self.assertRaises(RuntimeError):
                owner.verify_data()
            with self.assertRaises(RuntimeError):
                owner.remove()
            send.assert_not_called()
            remove.assert_not_called()

    def test_http_thread_failure_preserves_root(self):
        owner = self.owner()
        owner.pg_stopped = True
        owner.http_running = True
        with patch.object(owner, 'verify'), patch('shutil.rmtree') as remove, patch('os.close'):
            with self.assertRaisesRegex(RuntimeError, 'HTTP_STILL_RUNNING'):
                owner.remove()
            remove.assert_not_called()

    def test_tool_timeout_preserves_root_and_child_signal_mask_is_reset(self):
        import subprocess
        from backend.tests.test_v26_identity_postgres import V26IdentityPostgres
        class Fixture(V26IdentityPostgres):
            owned = Mock(pg_stopped=True)
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('synthetic', 40)) as run, \
             patch('signal.pthread_sigmask') as mask:
            with self.assertRaises(subprocess.TimeoutExpired):
                Fixture.run_pg(['synthetic-unit-command'])
            self.assertFalse(Fixture.owned.pg_stopped)
            run.call_args.kwargs['preexec_fn']()
            mask.assert_any_call(signal.SIG_UNBLOCK, {signal.SIGINT, signal.SIGTERM})

    def test_suspicious_or_symlinked_root_cannot_be_removed(self):
        owner = self.owner()
        owner.pg_stopped = True
        owner.suspicious = True
        with patch.object(owner, 'verify'), patch('shutil.rmtree') as remove, patch('os.close'):
            with self.assertRaisesRegex(RuntimeError, 'UNCONFIRMED'):
                owner.remove()
            remove.assert_not_called()
