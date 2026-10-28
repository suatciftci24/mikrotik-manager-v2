"""HTTP readiness/lifecycle contracts without sockets, services or databases."""
import asyncio
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import URLError, HTTPError
import errno
import json
from app import demo_readiness as readiness
from app import demo_api_runner as runner
from app import demo_acceptance as acceptance
from app.demo_repair import RepairBlocked
from app.main import ready


class Response:
    def __init__(self,payload):self.payload=payload
    def read(self):return json.dumps(self.payload).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass


class ReadinessTests(TestCase):
    def test_ready_identity_does_not_ping_database(self):
        with patch('app.services.demo_subscriptions.store') as store:
            data=asyncio.run(ready())
            store.ping.assert_not_called();store.list_items.assert_not_called()
        status=readiness.probe_api(SimpleNamespace(open=lambda *a,**k:Response(data)))
        self.assertEqual(status.state,'READY');self.assertFalse(data['database_checked'])

    def test_connection_refused_permission_and_timeout_are_distinct(self):
        for reason,state,word in [(ConnectionRefusedError(errno.ECONNREFUSED,'refused'),'ABSENT','reddedildi'),
                                  (PermissionError(errno.EPERM,'denied'),'BLOCKED','sandbox'),
                                  (TimeoutError('timeout'),'BLOCKED','zaman')]:
            client=SimpleNamespace(open=Mock(side_effect=URLError(reason)))
            status=readiness.probe_api(client)
            self.assertEqual(status.state,state);self.assertIn(word,status.detail)
            client.open.assert_called_once()

    def test_existing_wrong_or_legacy_service_never_counts_ready(self):
        for client in [SimpleNamespace(open=lambda *a,**k:Response({'environment':'local-demo'})),
                       SimpleNamespace(open=Mock(side_effect=HTTPError('http://127.0.0.1:8000',404,'',{},None)))]:
            self.assertEqual(readiness.probe_api(client).state,'WRONG')
        with self.assertRaises(ValueError):readiness.NoRedirect().redirect_request()

    def test_bounded_wait_only_retries_refused_connections_for_new_child(self):
        probe=Mock(side_effect=[readiness.APIStatus('ABSENT','starting'),readiness.APIStatus('READY','ok')])
        sleeps=[]
        status=readiness.wait_ready(lambda:True,probe=probe,clock=lambda:0,sleep=sleeps.append)
        self.assertEqual(status.state,'READY');self.assertEqual(sleeps,[0.2])
        blocked=Mock(return_value=readiness.APIStatus('BLOCKED','permission'))
        self.assertEqual(readiness.wait_ready(lambda:True,probe=blocked).state,'BLOCKED')
        blocked.assert_called_once()
        absent=Mock(return_value=readiness.APIStatus('ABSENT','starting'))
        clock=Mock(side_effect=[0,13])
        self.assertEqual(readiness.wait_ready(lambda:True,probe=absent,clock=clock,sleep=Mock()).state,'BLOCKED')
        absent.assert_called_once()
        dead=Mock()
        self.assertEqual(readiness.wait_ready(lambda:False,probe=dead).state,'BLOCKED');dead.assert_not_called()

    def test_existing_ready_api_is_never_started_or_stopped(self):
        with patch.object(runner,'probe_api',return_value=readiness.APIStatus('READY','ok')), \
             patch.object(runner.subprocess,'Popen') as start,patch.object(runner.socket,'socket') as socket, \
             redirect_stdout(StringIO()):
            with runner.ManagedAPI():pass
            start.assert_not_called();socket.assert_not_called()

    def test_wrong_service_and_socket_permission_stop_before_start(self):
        with patch.object(runner,'probe_api',return_value=readiness.APIStatus('WRONG','other')), \
             patch.object(runner.subprocess,'Popen') as start:
            with self.assertRaises(RepairBlocked):runner.ManagedAPI().__enter__()
            start.assert_not_called()
        with patch.object(runner,'probe_api',return_value=readiness.APIStatus('ABSENT','refused')), \
             patch.object(runner.socket,'socket',side_effect=PermissionError()), \
             patch.object(runner.subprocess,'Popen') as start:
            with self.assertRaises(RepairBlocked):runner.ManagedAPI().__enter__()
            start.assert_not_called()

    def test_cleanup_only_operates_on_own_child(self):
        managed=runner.ManagedAPI();child=Mock();child.poll.return_value=None;managed.process=child
        managed.stop();child.terminate.assert_called_once();child.wait.assert_called_once_with(timeout=5)
        dead=Mock();dead.poll.return_value=1;managed.process=dead
        managed.stop();dead.terminate.assert_not_called()

    def test_acceptance_unready_stops_before_db_capture_or_writes(self):
        with patch.object(acceptance,'require_api_ready',side_effect=RepairBlocked('API absent')), \
             patch.object(acceptance,'verify_database') as db,patch.object(acceptance,'Acceptance') as run, \
             redirect_stderr(StringIO()):
            self.assertEqual(acceptance.main([]),1)
            db.assert_not_called();run.assert_not_called()

    def test_new_api_uses_only_repo_venv_and_loopback_then_cleans_own_child(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            root=Path(folder);child=Mock();child.poll.return_value=None
            with patch.object(runner,'ROOT',root),patch.object(runner,'probe_api',return_value=readiness.APIStatus('ABSENT','refused')), \
                 patch.object(runner.socket,'socket'),patch.object(runner.subprocess,'Popen',return_value=child) as start, \
                 patch.object(runner,'wait_ready',return_value=readiness.APIStatus('READY','ok')),redirect_stdout(StringIO()):
                with runner.ManagedAPI() as managed:
                    log=managed.log_path
                command=start.call_args.args[0]
                self.assertEqual(command[:3],[str(root/'.venv/bin/python'),'-m','uvicorn'])
                self.assertEqual(command[-4:],['--host','127.0.0.1','--port','8000'])
                self.assertEqual(start.call_args.kwargs['cwd'],root)
                child.terminate.assert_called_once()
                self.assertTrue(log.is_file())

    def test_failed_new_child_readiness_stops_child_and_preserves_log(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            child=Mock();child.poll.return_value=None;root=Path(folder)
            with patch.object(runner,'ROOT',root),patch.object(runner,'probe_api',return_value=readiness.APIStatus('ABSENT','refused')), \
                 patch.object(runner.socket,'socket'),patch.object(runner.subprocess,'Popen',return_value=child), \
                 patch.object(runner,'wait_ready',return_value=readiness.APIStatus('BLOCKED','startup failed')),redirect_stderr(StringIO()):
                managed=runner.ManagedAPI()
                with self.assertRaises(RepairBlocked):managed.__enter__()
                child.terminate.assert_called_once()
                self.assertTrue(managed.log_path.is_file())
