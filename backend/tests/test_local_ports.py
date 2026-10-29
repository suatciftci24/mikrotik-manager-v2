"""Port overrides and bind diagnostics without real sockets or services."""
import errno
from unittest import TestCase
from unittest.mock import patch, Mock
from app.local_ports import api_port, ui_port
from app import demo_api_runner as runner, demo_readiness as readiness
from app.demo_repair import RepairBlocked


class LocalPortsTests(TestCase):
    def test_alternative_ports_reach_commands_and_http_probes(self):
        with patch.dict('os.environ', {'V2_API_PORT':'18000','V2_UI_PORT':'15173'}):
            self.assertEqual(api_port(),18000);self.assertEqual(ui_port(),15173)
            self.assertEqual(runner.ManagedAPI().command()[-1],'18000')
            client=Mock();client.open.side_effect=ConnectionRefusedError(errno.ECONNREFUSED,'closed')
            self.assertEqual(readiness.probe_api(client).state,'ABSENT')
            self.assertEqual(client.open.call_args.args[0].full_url,'http://127.0.0.1:18000/api/ready')
            self.assertEqual(readiness.probe_ui(client).state,'ABSENT')
            self.assertEqual(client.open.call_args.args[0].full_url,'http://127.0.0.1:15173/')

    def test_invalid_or_equal_ports_fail_before_start(self):
        for raw in ('0','80','65536','localhost:8000','-1',''):
            with patch.dict('os.environ',{'V2_API_PORT':raw}):
                with self.assertRaises(ValueError):api_port()
        with patch.dict('os.environ',{'V2_API_PORT':'18000','V2_UI_PORT':'18000'}):
            with self.assertRaises(ValueError):ui_port()

    def test_bind_errors_are_distinct_and_never_start_or_stop_other_processes(self):
        for code,expected in [(errno.EADDRINUSE,'PORT_IN_USE'),(errno.EPERM,'SOCKET_PERMISSION_DENIED'),
                              (errno.EADDRNOTAVAIL,'BIND_ADDRESS_UNAVAILABLE'),(errno.EMFILE,'SOCKET_ERROR')]:
            with self.subTest(code=code),patch.object(runner,'probe_api',return_value=readiness.APIStatus('ABSENT','closed')), \
                 patch.object(runner.socket,'socket') as sock,patch.object(runner.subprocess,'Popen') as start:
                sock.return_value.__enter__.return_value.bind.side_effect=OSError(code,'fixture')
                with self.assertRaisesRegex(RepairBlocked,expected):runner.ManagedAPI().__enter__()
                start.assert_not_called()
                sock.return_value.__enter__.return_value.setsockopt.assert_called_once_with(runner.socket.SOL_SOCKET,runner.socket.SO_REUSEADDR,1)
