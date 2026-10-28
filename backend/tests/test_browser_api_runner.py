"""Browser dispatch must reuse Stage 9 API ownership; no real sockets or browser launch."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from app import demo_api_runner as runner
from app.demo_repair import RepairBlocked


class BrowserAPIReuse(TestCase):
    def test_browser_runs_only_inside_shared_manager_and_uses_nonrecursive_worker(self):
        order=[]
        class Manager:
            def __enter__(self):order.append('ready');return self
            def __exit__(self,*args):order.append('cleanup')
        def worker(command,**kwargs):
            self.assertEqual(order,['ready'])
            self.assertEqual(command,[str(runner.ROOT/'browser-accept-demo.sh'),'--with-ready-services'])
            self.assertEqual(kwargs['cwd'],runner.ROOT)
            order.append('browser')
            return SimpleNamespace(returncode=0)
        with patch.object(runner,'ManagedAPI',Manager),patch.object(runner,'ManagedUI'), \
             patch.object(runner,'require_browser_database'),patch.object(runner.subprocess,'run',side_effect=worker):
            self.assertEqual(runner.main(['--browser']),0)
        self.assertEqual(order,['ready','browser','cleanup'])

    def test_browser_failure_code_preserved_and_manager_still_cleans_up(self):
        with patch.object(runner,'ManagedAPI') as manager, patch.object(runner,'ManagedUI') as ui, \
             patch.object(runner,'require_browser_database'), \
             patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=7)):
            self.assertEqual(runner.main(['--browser']),7)
            manager.return_value.__exit__.assert_called_once();ui.return_value.__exit__.assert_called_once()

    def test_readiness_blocker_prevents_browser_tools_and_test_records(self):
        with patch.object(runner,'ManagedAPI') as manager,patch.object(runner.subprocess,'run') as worker,redirect_stderr(StringIO()):
            manager.return_value.__enter__.side_effect=RepairBlocked('sandbox')
            self.assertEqual(runner.main(['--browser']),1)
            worker.assert_not_called()

    def test_original_stage9_dispatch_still_uses_same_manager_without_browser_worker(self):
        with patch.object(runner,'ManagedAPI') as manager,patch.object(runner.subprocess,'run') as worker, \
             patch('app.demo_acceptance.main',return_value=0) as accept:
            self.assertEqual(runner.main([]),0)
            accept.assert_called_once_with([]);worker.assert_not_called()
            manager.return_value.__exit__.assert_called_once()

    def test_help_never_starts_an_api_or_browser(self):
        with patch.object(runner,'ManagedAPI') as manager,patch.object(runner.subprocess,'run') as worker,redirect_stdout(StringIO()):
            with self.assertRaises(SystemExit) as result:runner.main(['--browser','--help'])
            self.assertEqual(result.exception.code,0)
            manager.assert_not_called();worker.assert_not_called()

    def test_db_blocker_prevents_ui_tools_and_writes_but_cleans_owned_api(self):
        with patch.object(runner,'ManagedAPI') as api,patch.object(runner,'ManagedUI') as ui, \
             patch.object(runner,'require_browser_database',side_effect=RepairBlocked('DB not ready')), \
             patch.object(runner.subprocess,'run') as worker,redirect_stderr(StringIO()):
            self.assertEqual(runner.main(['--browser']),1)
            ui.assert_not_called();worker.assert_not_called();api.return_value.__exit__.assert_called_once()

    def test_dev_reuses_managers_without_database_or_acceptance(self):
        with patch.object(runner,'ManagedAPI') as api,patch.object(runner,'ManagedUI') as ui, \
             patch.object(runner,'require_browser_database') as db, \
             patch.object(runner.subprocess,'run') as worker, \
             patch.object(runner.time,'sleep',side_effect=KeyboardInterrupt), \
             patch('app.demo_acceptance.main') as accept,redirect_stdout(StringIO()):
            api.return_value.__enter__.return_value.process=None
            ui.return_value.__enter__.return_value.process=None
            self.assertEqual(runner.main(['--dev']),130)
            db.assert_not_called();worker.assert_not_called();accept.assert_not_called()
            api.return_value.__exit__.assert_called_once();ui.return_value.__exit__.assert_called_once()

    def test_sigterm_handler_is_restored_after_cleanup(self):
        import signal
        previous=signal.getsignal(signal.SIGTERM)
        def terminate(_seconds):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        with patch.object(runner,'ManagedAPI') as api,patch.object(runner,'ManagedUI') as ui, \
             patch.object(runner.time,'sleep',side_effect=terminate),redirect_stdout(StringIO()):
            api.return_value.__enter__.return_value.process=None
            ui.return_value.__enter__.return_value.process=None
            self.assertEqual(runner.main(['--dev']),130)
            api.return_value.__exit__.assert_called_once();ui.return_value.__exit__.assert_called_once()
        self.assertIs(signal.getsignal(signal.SIGTERM),previous)

    def test_alarm_acceptance_prepares_one_explicit_fixture_inside_existing_service_lifecycle(self):
        with patch.object(runner,'ManagedAPI') as api,patch.object(runner,'ManagedUI') as ui, \
             patch.object(runner,'require_browser_database'), \
             patch('app.demo_storage.prepare_alarm_acceptance',return_value='demo-sub-test-new') as setup, \
             patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as worker,redirect_stdout(StringIO()):
            self.assertEqual(runner.main(['--browser','--alarm-acceptance']),0)
            setup.assert_called_once();api.return_value.__exit__.assert_called_once();ui.return_value.__exit__.assert_called_once()
            env=worker.call_args.kwargs['env']
            self.assertEqual(env['V2_BROWSER_ALARMS_ACK'],'1')
            self.assertEqual(env['V2_BROWSER_ALARMS_ONLY'],'1')
            self.assertEqual(env['V2_ALARM_TEST_SUBSCRIBER'],'demo-sub-test-new')

    def test_blocked_database_never_prepares_alarm_schema_or_fixture(self):
        with patch.object(runner,'ManagedAPI'),patch.object(runner,'ManagedUI') as ui, \
             patch.object(runner,'require_browser_database',side_effect=RepairBlocked('DB not ready')), \
             patch('app.demo_storage.prepare_alarm_acceptance') as setup,redirect_stderr(StringIO()):
            self.assertEqual(runner.main(['--browser','--alarm-acceptance']),1)
            setup.assert_not_called();ui.assert_not_called()
