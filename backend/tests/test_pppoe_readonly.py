from unittest import TestCase
from unittest.mock import Mock, patch
from app.adapters.pppoe_readonly import RouterReadSettings, ReadConfigurationError, PppoeReadAdapter


class PppoeReadTests(TestCase):
    def config(self):
        env = dict(V2_ROUTER_READ_ADDRESS='192.0.2.1', V2_ROUTER_READ_USERNAME='fixture-reader',
                   V2_ROUTER_READ_PASSWORD='synthetic-password', V2_ROUTER_READ_CA_PEM='synthetic-ca',
                   V2_ROUTER_READ_LEAF_SHA256='a' * 64)
        self.env = env
        with patch.dict('os.environ', env, clear=True), patch('socket.socket', side_effect=AssertionError('network forbidden')):
            return RouterReadSettings.environment()

    def test_config_no_io_and_no_credentials_in_repr(self):
        config = self.config()
        self.assertNotIn('synthetic-password', repr(config))
        self.assertNotIn('fixture-reader', repr(config))
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(ReadConfigurationError, '^ROUTER_READ_CONFIG_INVALID$'):
                RouterReadSettings.environment()

    def test_bounds_and_nonfinite_timeout(self):
        self.config()
        for timeout in ('nan', 'inf', '0', '11'):
            with patch.dict('os.environ', {**self.env, 'V2_ROUTER_READ_TIMEOUT_SECONDS': timeout}, clear=True):
                with self.assertRaises(ReadConfigurationError):
                    RouterReadSettings.environment()

    def test_explicit_authority_unknown_session_and_empty_result(self):
        transport = Mock()
        transport.read_pppoe.return_value = [dict(account_id='account-1', source='RADIUS')]
        result = PppoeReadAdapter(transport).read(self.config())
        self.assertEqual(result.availability, 'AVAILABLE')
        self.assertEqual(result.items[0].source, 'RADIUS')
        self.assertIsNone(result.items[0].connected)
        self.assertFalse(result.is_demo)
        transport.read_pppoe.return_value = []
        self.assertEqual(PppoeReadAdapter(transport).read(self.config()).items, ())

    def test_missing_ambiguous_duplicate_and_sensitive_data_fail_closed(self):
        row = dict(account_id='account-1', source='LOCAL')
        for rows in ([{}], [{**row, 'source': 'UNKNOWN'}], [row, row], [row] * 129,
                     [{**row, 'password': 'synthetic-password'}], [{**row, 'account_id': 'synthetic-password'}], None):
            transport = Mock(); transport.read_pppoe.return_value = rows
            result = PppoeReadAdapter(transport).read(self.config())
            self.assertEqual(result.error, 'INVALID_DATA'); self.assertEqual(result.items, ())

    def test_transport_failure_redacted_without_retry(self):
        for error, code in ((TimeoutError('sensitive'), 'TIMEOUT'), (OSError('sensitive'), 'CONNECTION_FAILED')):
            transport = Mock(); transport.read_pppoe.side_effect = error
            result = PppoeReadAdapter(transport).read(self.config())
            self.assertEqual(result.error, code); self.assertNotIn('sensitive', repr(result))
            transport.read_pppoe.assert_called_once()
