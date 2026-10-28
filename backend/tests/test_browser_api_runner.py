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
            self.assertEqual(command,[str(runner.ROOT/'browser-accept-demo.sh'),'--with-ready-api'])
            self.assertEqual(kwargs['cwd'],runner.ROOT)
            order.append('browser')
            return SimpleNamespace(returncode=0)
        with patch.object(runner,'ManagedAPI',Manager),patch.object(runner.subprocess,'run',side_effect=worker):
            self.assertEqual(runner.main(['--browser']),0)
        self.assertEqual(order,['ready','browser','cleanup'])

    def test_browser_failure_code_preserved_and_manager_still_cleans_up(self):
        with patch.object(runner,'ManagedAPI') as manager, \
             patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=7)):
            self.assertEqual(runner.main(['--browser']),7)
            manager.return_value.__exit__.assert_called_once()

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
