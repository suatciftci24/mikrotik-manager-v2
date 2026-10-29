"""Source-aware readiness and guarded refresh; no actual signal or network access."""
import asyncio,json,os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from app import demo_readiness as readiness, local_refresh as refresh
from app.demo_repair import RepairBlocked
from app.main import ready

class Response:
    def __init__(self,data):self.data=data
    def read(self):return json.dumps(self.data).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass

class RefreshTests(TestCase):
    def test_legacy_ready_and_wrong_build_never_reuse_stale_api(self):
        current=asyncio.run(ready())
        for payload,state in [(current,'READY'),({k:v for k,v in current.items() if k not in ('build_id','repo_id','router_workspace_version')},'STALE'),({**current,'build_id':'old'},'STALE'),({**current,'repo_id':'other'},'STALE'),({**current,'api_port':18099},'STALE')]:
            client=SimpleNamespace(open=lambda *a,**k:Response(payload))
            self.assertEqual(readiness.probe_api(client).state,state)
    def test_permission_block_prevents_process_scanning_and_signals(self):
        with patch.object(refresh,'socket_permission',side_effect=RepairBlocked('sandbox')),patch.object(refresh,'listener_inodes') as scan,patch.object(refresh.signal,'pidfd_send_signal') as signal:
            with self.assertRaises(RepairBlocked):refresh.refresh()
            scan.assert_not_called();signal.assert_not_called()
    def test_foreign_api_refusal_leaves_valid_project_ui_untouched(self):
        with patch.object(refresh,'socket_permission'),patch.object(refresh,'listener_inodes',return_value={'1'}),patch.object(refresh,'owner',return_value=321),patch.object(refresh,'identity',side_effect=[('ui',),('ui',),RepairBlocked('foreign api')]),patch.object(refresh.os,'pidfd_open',return_value=88),patch.object(refresh.os,'close') as close,patch.object(refresh.signal,'pidfd_send_signal') as signal:
            with self.assertRaises(RepairBlocked):refresh.refresh()
            signal.assert_not_called();close.assert_called_once_with(88)
    def test_only_validated_handles_receive_sigterm_and_never_sigkill(self):
        with patch.object(refresh,'socket_permission'),patch.object(refresh,'listener_inodes',return_value={'1'}),patch.object(refresh,'owner',return_value=321),patch.object(refresh,'identity',return_value=('owned',)),patch.object(refresh.os,'pidfd_open',side_effect=[88,89]),patch.object(refresh.os,'close') as close,patch.object(refresh.signal,'pidfd_send_signal') as signal,patch.object(refresh.select,'select',side_effect=[([88],[],[]),([89],[],[])]):
            refresh.refresh()
            self.assertEqual([c.args for c in signal.call_args_list],[(88,refresh.signal.SIGTERM),(89,refresh.signal.SIGTERM)])
            self.assertEqual(close.call_count,2)
    def test_process_identity_rejects_other_checkout_or_changed_port(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);proc=root/'proc';pid=proc/'321';pid.mkdir(parents=True)
            (root/'.venv/bin').mkdir(parents=True);(root/'.venv/bin/python').touch()
            (pid/'cwd').symlink_to(root,target_is_directory=True)
            argv=[str(root/'.venv/bin/python'),'-m','uvicorn','app.main:app','--app-dir',str(root/'backend'),'--host','127.0.0.1','--port','18000']
            (pid/'cmdline').write_bytes(('\0'.join(argv)+'\0').encode());(pid/'stat').write_text('321 (python) '+' '.join(['S']+['0']*18+['123']))
            with patch.object(refresh,'ROOT',root):
                self.assertEqual(refresh.identity(321,'API',18000,proc)[-1],'123')
                with self.assertRaises(RepairBlocked):refresh.identity(321,'API',18001,proc)
            with patch.object(refresh,'ROOT',root/'other'):
                with self.assertRaises(RepairBlocked):refresh.identity(321,'API',18000,proc)

    def test_workspace_paths_are_registered_with_the_frontend_methods(self):
        from app.main import app
        from starlette.routing import Match
        for path,method in [('/api/v1/router-workspace/routers','GET'),('/api/v1/router-workspace/routers','POST'),('/api/v1/router-workspace/routers/demo-managed-router-fixture','GET'),('/api/v1/router-workspace/routers/demo-managed-router-fixture','POST'),('/api/v1/router-workspace/routers/demo-managed-router-fixture/delete','POST')]:
            self.assertTrue(any(route.matches({'type':'http','path':path,'root_path':'','method':method})[0]==Match.FULL for route in app.routes),path)

    def test_listener_scan_accepts_only_loopback_and_never_wildcard(self):
        with TemporaryDirectory() as folder:
            proc=Path(folder);(proc/'net').mkdir()
            file=proc/'net/tcp'
            file.write_text('header\n0: 0100007F:4650 00000000:0000 0A 0:0 00:0 0 1000 0 12345\n')
            self.assertEqual(refresh.listener_inodes(18000,proc),{'12345'})
            self.assertEqual(refresh.listener_inodes(18001,proc),set())
            file.write_text(file.read_text().replace('0100007F','00000000'))
            with self.assertRaises(RepairBlocked):refresh.listener_inodes(18000,proc)
