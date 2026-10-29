"""Shared UI lifecycle and Vite identity, without launching services or sockets."""
import json
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import URLError
from app import demo_api_runner as runner
from app import demo_readiness as readiness
from app.runtime_identity import BUILD_ID,REPO_ID
from app.demo_repair import RepairBlocked


class HTML:
    def __init__(self,body):self.body=body
    def read(self):return self.body
    def __enter__(self):return self
    def __exit__(self,*args):pass


class ManagedUITests(TestCase):
    def test_ui_identity_requires_actual_vite_entry_not_just_a_page(self):
        for body,state in [(b'<title>MikroTik Manager V2</title><script src="/src/main.tsx"></script>','READY'),
                           (b'<title>Other application</title>','WRONG'),(b'MikroTik Manager V2','WRONG')]:
            def response(request,**kwargs):
                if request.full_url.endswith('/@vite/client'):return HTML(b'vite client')
                if request.full_url.endswith('/api/ready'):
                    return HTML(json.dumps(dict(service='mikrotik-manager-v2',environment='local-demo',api_version='v1',database_checked=False,api_port=8000,repo_id=REPO_ID,build_id=BUILD_ID,router_workspace_version=1)).encode())
                return HTML(body)
            client=SimpleNamespace(open=response)
            self.assertEqual(readiness.probe_ui(client).state,state)
        client=SimpleNamespace(open=Mock(side_effect=URLError(ConnectionRefusedError(111,'refused'))))
        result=readiness.probe_ui(client)
        self.assertEqual(result.state,'ABSENT');self.assertIn('5173',result.detail);self.assertNotIn('8000',result.detail)

    def test_existing_ready_ui_is_untouched(self):
        with patch.object(runner,'probe_ui',return_value=readiness.APIStatus('READY','ok')), \
             patch.object(runner.socket,'socket') as socket,patch.object(runner.subprocess,'Popen') as start,redirect_stdout(StringIO()):
            with runner.ManagedUI():pass
            socket.assert_not_called();start.assert_not_called()

    def test_new_ui_reuses_dev_entrypoint_and_cleans_only_owned_vite_pid(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);entry=root/'frontend/node_modules/vite/bin/vite.js';entry.parent.mkdir(parents=True);entry.touch()
            child=Mock();child.poll.return_value=None
            with patch.object(runner,'ROOT',root),patch.object(runner,'probe_ui',return_value=readiness.APIStatus('ABSENT','closed')), \
                 patch.object(runner.socket,'socket') as socket,patch.object(runner.subprocess,'Popen',return_value=child) as start, \
                 patch.object(runner,'wait_ready',return_value=readiness.APIStatus('READY','ok')) as wait,redirect_stdout(StringIO()):
                with runner.ManagedUI() as managed:log=managed.log_path
                self.assertEqual(start.call_args.args[0],[str(root/'dev.sh'),'--ui-only'])
                socket.return_value.__enter__.return_value.bind.assert_called_once_with(('127.0.0.1',5173))
                self.assertEqual(wait.call_args.kwargs['label'],'UI')
                child.terminate.assert_called_once();self.assertTrue(log.is_file())

    def test_wrong_or_permission_blocked_ui_is_never_started(self):
        for state in ('WRONG','BLOCKED'):
            with patch.object(runner,'probe_ui',return_value=readiness.APIStatus(state,'blocked')),patch.object(runner.subprocess,'Popen') as start:
                with self.assertRaises(RepairBlocked):runner.ManagedUI().__enter__()
                start.assert_not_called()

    def test_ui_startup_failure_cleans_child_and_preserves_log(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);entry=root/'frontend/node_modules/vite/bin/vite.js';entry.parent.mkdir(parents=True);entry.touch()
            child=Mock();child.poll.return_value=None
            with patch.object(runner,'ROOT',root),patch.object(runner,'probe_ui',return_value=readiness.APIStatus('ABSENT','closed')), \
                 patch.object(runner.socket,'socket'),patch.object(runner.subprocess,'Popen',return_value=child), \
                 patch.object(runner,'wait_ready',return_value=readiness.APIStatus('BLOCKED','UI failed')),redirect_stderr(StringIO()):
                manager=runner.ManagedUI()
                with self.assertRaises(RepairBlocked):manager.__enter__()
                child.terminate.assert_called_once();self.assertTrue(manager.log_path.is_file())

    def test_db_gate_is_read_only_and_checks_running_api_database_health(self):
        with patch('app.demo_repair.verify_database',return_value=(None,[{}])) as database, \
             patch('app.demo_repair.LocalHTTP') as http,redirect_stdout(StringIO()):
            http.return_value.request.return_value=dict(environment='local-demo',database_connected=False,device_adapters_connected=False)
            with self.assertRaises(RepairBlocked):runner.require_browser_database()
            database.assert_called_once();http.return_value.request.assert_called_once_with('/api/health')

    def test_ui_rejects_wrong_vite_or_proxy_identity(self):
        page=b'<title>MikroTik Manager V2</title>/src/main.tsx'
        for vite,api in [(b'other',b'{}'),(b'vite',b'{}'),(b'vite',b'[]')]:
            client=SimpleNamespace(open=Mock(side_effect=[HTML(page),HTML(vite),HTML(api)]))
            self.assertEqual(readiness.probe_ui(client).state,'WRONG')

    def test_proxy_permission_failure_is_not_retried(self):
        page=b'<title>MikroTik Manager V2</title>/src/main.tsx'
        client=SimpleNamespace(open=Mock(side_effect=[HTML(page),HTML(b'vite'),URLError(PermissionError(1,'denied'))]))
        self.assertEqual(readiness.probe_ui(client).state,'BLOCKED')
        self.assertEqual(client.open.call_count,3)
