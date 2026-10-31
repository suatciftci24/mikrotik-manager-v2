"""Synthetic wire/TLS tests only: no socket may reach a network."""
import hashlib
import ssl
from unittest import TestCase
from unittest.mock import Mock, patch
from pydantic import SecretStr
from app.adapters.cebeci_api_ssl import _encoded_word, ApiSslStop
from app.adapters.pppoe_api_ssl import PppoeAccount, _PppoeWire, _QUERY
from app.adapters.pppoe_readonly import RouterReadSettings
from app.adapters.router_api_ssl import ConnectionPolicy
from app.services.pppoe_readonly import api_ssl_binding, snapshot


def packet(*words):
    return b''.join(_encoded_word(w) for w in words) + b'\0'


class PppoeApiSslTests(TestCase):
    def setUp(self):
        self.settings = RouterReadSettings('192.0.2.1', 'fixture-reader', SecretStr('synthetic-password'),
                                           'synthetic-ca', hashlib.sha256(b'cert').hexdigest())
        self.policy = ConnectionPolicy(True, '192.0.2.2', ('192.0.2.0/24',))
        self.accounts = (PppoeAccount('a1', 'fixture-local', 'LOCAL'), PppoeAccount('a2', 'fixture-radius', 'RADIUS'))
        self.raw = Mock()
        self.secure = Mock()
        self.secure.getpeername.return_value = ('192.0.2.1', 8729)
        self.secure.getsockname.return_value = ('192.0.2.2', 10000)
        self.secure.version.return_value = 'TLSv1.2'
        self.secure.getpeercert.side_effect = lambda binary_form=False: b'cert' if binary_form else {'subjectAltName': (('IP Address', '192.0.2.1'),)}
        self.context = Mock(verify_mode=ssl.CERT_REQUIRED, check_hostname=True,
                            minimum_version=ssl.TLSVersion.TLSv1_2, hostname_checks_common_name=False)
        self.context.wrap_socket.return_value = self.secure
        self.patches = [patch('app.adapters.pppoe_api_ssl.socket.socket', return_value=self.raw),
                        patch('app.adapters.pppoe_api_ssl.verified_tls_context', return_value=self.context)]
        for p in self.patches:
            p.start(); self.addCleanup(p.stop)

    def response(self, *sentences):
        data = bytearray(b''.join(packet(*s) for s in sentences))
        def recv(size):
            # Fragmented delivery exercises timeout resets and framing.
            size = min(size, 2)
            out = bytes(data[:size]); del data[:size]; return out
        self.secure.recv.side_effect = recv

    def read(self, policy=None, router='router-1'):
        binding = api_ssl_binding('router-1', self.settings, self.accounts, policy or self.policy)
        return snapshot(router, is_demo=False, binding=binding)

    def test_modern_login_fixed_read_authorities_and_freshness(self):
        for version in ('TLSv1.2', 'TLSv1.3'):
            self.secure.version.return_value = version
            self.secure.sendall.reset_mock()
            self.response(('!done',), ('!re', '=name=fixture-local', '=service=pppoe', '=address=192.0.2.10', '=radius=false'),
                          ('!re', '=name=fixture-radius', '=service=pppoe', '=address=192.0.2.11', '=radius=true'), ('!done',))
            result = self.read()
            self.assertEqual(result.availability, 'AVAILABLE')
            self.assertEqual([i.source for i in result.items], ['LOCAL', 'RADIUS'])
            self.assertTrue(all(i.source_status == 'FRESH' for i in result.items))
            self.assertNotIn('fixture-local', result.model_dump_json())
            self.assertEqual(len(self.secure.sendall.call_args_list), 2)
            self.assertEqual(self.secure.sendall.call_args_list[1].args[0], packet(*_QUERY))
            self.raw.close.assert_called(); self.secure.close.assert_called()

    def test_disabled_wrong_router_and_demo_do_not_connect(self):
        binding = api_ssl_binding('router-1', self.settings, self.accounts)
        for demo, router in ((False, 'router-1'), (False, 'other'), (True, 'router-1')):
            self.assertEqual(snapshot(router, is_demo=demo, binding=binding).availability, 'UNAVAILABLE')
        self.context.wrap_socket.assert_not_called(); self.raw.connect.assert_not_called()

    def test_empty_v7_has_no_invented_measurement(self):
        self.response(('!done',), ('!empty',), ('!done',))
        result = self.read()
        self.assertEqual(result.availability, 'AVAILABLE')
        self.assertEqual(result.items, []); self.assertIsNone(result.last_successful_observed_at)

    def test_mismatch_duplicates_extra_sensitive_fields_fail_without_partial_rows(self):
        local = ('!re', '=name=fixture-local', '=service=pppoe', '=address=192.0.2.10', '=radius=false')
        for rows in ((local, local), (local, ('!re', '=name=fixture-radius', '=service=pppoe', '=address=192.0.2.11', '=radius=false')),
                     (local + ('=password=synthetic-password',),), (('!trap', '=message=synthetic-password'),)):
            self.response(('!done',), *rows, ('!done',))
            result = self.read()
            self.assertEqual(result.availability, 'UNAVAILABLE'); self.assertEqual(result.items, [])
            self.assertNotIn('synthetic-password', result.model_dump_json())

    def test_tls_failure_precedes_credentials_and_closes(self):
        self.secure.getpeercert.side_effect = lambda binary_form=False: b'wrong' if binary_form else {}
        self.assertEqual(self.read().error, 'CONNECTION_FAILED')
        self.secure.sendall.assert_not_called(); self.secure.close.assert_called()

    def test_connect_and_read_timeout_cleanup(self):
        self.raw.connect.side_effect = TimeoutError('sensitive')
        self.assertEqual(self.read().error, 'TIMEOUT'); self.raw.close.assert_called()
        self.raw.connect.side_effect = None
        self.secure.recv.side_effect = TimeoutError('sensitive')
        self.assertEqual(self.read().error, 'TIMEOUT'); self.secure.close.assert_called()
        self.assertTrue(all(0 < c.args[0] <= 2 for c in self.secure.settimeout.call_args_list))

    def test_absolute_deadline_cannot_be_extended_by_chunks(self):
        self.response(('!done',), ('!done',))
        with patch('time.monotonic', side_effect=[0, 0, 0, 0, 0, 0, 3]):
            self.assertEqual(self.read().error, 'TIMEOUT')
        self.raw.close.assert_called()

    def test_wire_rejects_mutation_and_legacy_challenge(self):
        wire = _PppoeWire(self.secure, float('inf'), 1)
        for command in (('/ppp/secret/add',), ('/ppp/active/remove',), ('/system/reboot',), ('/ppp/secret/print',)):
            with self.assertRaises(ApiSslStop): wire.send(command)
        self.secure.sendall.assert_not_called()
        self.response(('!done', '=ret=' + 'ab'*16))
        with self.assertRaises(ApiSslStop): wire.login(credentials=('fixture-reader', 'synthetic-password'))

    def test_strict_tls_policy_before_network(self):
        for attribute, value in (('verify_mode', ssl.CERT_NONE), ('check_hostname', False),
                                 ('minimum_version', ssl.TLSVersion.TLSv1_1),
                                 ('hostname_checks_common_name', True)):
            with self.subTest(attribute=attribute), patch.object(self.context, attribute, value):
                self.assertEqual(self.read().error, 'CONNECTION_FAILED')
                self.raw.connect.assert_not_called()
                self.secure.sendall.assert_not_called()

    def test_handshake_certificate_failure_or_timeout_closes_raw(self):
        for error, expected in ((ssl.SSLCertVerificationError('synthetic expired/untrusted'), 'CONNECTION_FAILED'),
                                (TimeoutError('synthetic handshake'), 'TIMEOUT')):
            self.context.wrap_socket.side_effect = error
            result = self.read()
            self.assertEqual(result.error, expected)
            self.assertEqual(result.items, [])
            self.secure.sendall.assert_not_called()
            self.raw.close.assert_called()
            self.context.wrap_socket.assert_called_with(self.raw, server_hostname=self.settings.address)

    def test_san_endpoint_and_protocol_checked_before_login(self):
        for method, value in ((self.secure.getpeername, ('192.0.2.99', 8729)),
                              (self.secure.getsockname, ('192.0.2.99', 10000)),
                              (self.secure.version, 'TLSv1.1')):
            with patch.object(method, 'return_value', value):
                self.assertEqual(self.read().error, 'CONNECTION_FAILED')
                self.secure.sendall.assert_not_called()
                self.secure.close.assert_called()
        self.secure.getpeercert.side_effect = lambda binary_form=False: b'cert' if binary_form else {
            'subjectAltName': (('DNS', '192.0.2.1'),)}
        self.assertEqual(self.read().error, 'CONNECTION_FAILED')
        self.secure.sendall.assert_not_called()

    def test_allowlist_rejects_altered_print_commands(self):
        wire = _PppoeWire(self.secure, float('inf'), 1)
        for command in ((_QUERY[0],), _QUERY + ('?name=fixture-local',),
                        ('/ppp/active/print', '=.proplist=name,password'),
                        ('/system/resource/print',), ('/login',)):
            with self.assertRaises(ApiSslStop):
                wire.send(command)
        self.secure.sendall.assert_not_called()

    def test_exact_inventory_mapping_ignores_unknown_and_other_services(self):
        self.response(('!done',),
                      ('!re', '=name=unknown', '=service=pppoe', '=address=192.0.2.90', '=radius=false'),
                      ('!re', '=name=fixture-local', '=service=pptp', '=address=192.0.2.91', '=radius=false'),
                      ('!re', '=name=fixture-radius', '=service=pppoe', '=address=192.0.2.11', '=radius=yes'),
                      ('!done',))
        result = self.read()
        self.assertEqual(result.availability, 'AVAILABLE')
        self.assertEqual([(r.account_id, r.source) for r in result.items], [('a2', 'RADIUS')])
        self.assertTrue(result.items[0].connected)
        self.assertEqual(result.items[0].observed_at.utcoffset().total_seconds(), 0)

    def test_invalid_inventory_rejected_before_network(self):
        original = self.accounts
        for accounts in ((original[0], original[0]),
                         (original[0], PppoeAccount('a2', 'fixture-local', 'RADIUS')),
                         (PppoeAccount('a1', 'fixture-local', 'UNKNOWN'),)):
            self.accounts = accounts
            self.assertEqual(self.read().availability, 'UNAVAILABLE')
        self.raw.connect.assert_not_called()

    def test_contradictory_empty_response_rejected(self):
        row = ('!re', '=name=fixture-local', '=service=pppoe', '=address=192.0.2.10', '=radius=false')
        for sentences in ((('!empty',), row), (row, ('!empty',)), (('!empty',), ('!empty',))):
            self.response(('!done',), *sentences, ('!done',))
            result = self.read()
            self.assertEqual(result.error, 'INVALID_DATA')
            self.assertEqual(result.items, [])
            self.assertIsNone(result.last_successful_observed_at)

    def test_empty_and_timeout_keep_timestamp_without_cached_sessions(self):
        binding = api_ssl_binding('router-1', self.settings, self.accounts, self.policy)
        self.response(('!done',),
                      ('!re', '=name=fixture-local', '=service=pppoe', '=address=192.0.2.10', '=radius=no'),
                      ('!done',))
        first = snapshot('router-1', is_demo=False, binding=binding)
        self.assertIsNotNone(first.last_successful_observed_at)
        self.response(('!done',), ('!done',))
        empty = snapshot('router-1', is_demo=False, binding=binding)
        self.assertEqual(empty.availability, 'AVAILABLE')
        self.assertEqual(empty.items, [])
        self.assertEqual(empty.last_successful_observed_at, first.last_successful_observed_at)
        self.secure.recv.side_effect = TimeoutError('synthetic read')
        failure = snapshot('router-1', is_demo=False, binding=binding)
        self.assertEqual(failure.error, 'TIMEOUT')
        self.assertEqual(failure.items, [])
        self.assertEqual(failure.last_successful_observed_at, first.last_successful_observed_at)
