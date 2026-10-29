"""Synthetic RouterOS 6 login frames; no sockets, real passwords or router access."""
import time
from unittest import TestCase
from unittest.mock import patch
from app.adapters import cebeci_api_ssl as api
from backend.tests.test_cebeci_api_ssl import FakeTls,sentence

class LoginDiagnosticsTests(TestCase):
    def login(self,reply,password='SYNTHETIC_PASSWORD'):
        stream=FakeTls(reply)
        wire=api._Wire(stream,time.monotonic()+10,2)
        with patch.object(api,'_runtime_material',side_effect=lambda kind,limit:'v2-cebeci-ro' if kind=='USERNAME' else password):
            wire.login()
        return stream

    def test_ros6_success_exact_packet_utf8_and_two_byte_length(self):
        password='SYNTHETIC-'+('é'*80)+' =!$\\'
        stream=self.login(sentence('!done'),password)
        self.assertEqual(stream.sent,sentence('/login','=name=v2-cebeci-ro','=password='+password))
        # UTF-8 byte length, not character count; sentence ends in a zero word.
        self.assertEqual(api._encoded_word('é'*64)[:2],b'\x80\x80')
        self.assertTrue(stream.sent.endswith(b'\x00'))

    def test_credential_or_account_policy_is_ambiguous_not_category_six(self):
        reply=sentence('!trap','=message=invalid user name or password (6)')+sentence('!done')
        with self.assertRaisesRegex(api.ApiSslStop,'^AUTHENTICATION_REJECTED:TRAP:CREDENTIAL_OR_ACCOUNT_POLICY:MESSAGE_CODE_6:CATEGORY_NONE$'):
            self.login(reply)

    def test_explicit_permission_and_category_are_independent(self):
        for category in ('0','1','2','3','4','5','6','7','CANARY'):
            safe=category if category!='CANARY' else 'UNKNOWN'
            with self.assertRaisesRegex(api.ApiSslStop,'^AUTHENTICATION_REJECTED:TRAP:PERMISSION_DENIED:MESSAGE_CODE_9:CATEGORY_'+safe+'$'):
                self.login(sentence('!trap','=category='+category,'=message=not enough permissions (9)'))

    def test_unknown_fatal_malformed_and_challenge_never_echo_or_retry(self):
        cases=[
            (sentence('!trap','=message=password=SECRET_CANARY'),'AUTHENTICATION_REJECTED:TRAP:UNCLASSIFIED:CATEGORY_NONE'),
            (sentence('!fatal','SECRET_CANARY'),'AUTHENTICATION_REJECTED:FATAL:UNCLASSIFIED'),
            (sentence('!trap','=message=a','=message=SECRET_CANARY'),'AUTHENTICATION_REJECTED:TRAP:UNCLASSIFIED'),
            (sentence('!done','=ret=SECRET_CANARY'),'AUTHENTICATION_PROTOCOL_ERROR:LEGACY_CHALLENGE_UNSUPPORTED'),
            (sentence('!done','=unexpected=SECRET_CANARY'),'AUTHENTICATION_PROTOCOL_ERROR:UNEXPECTED_REPLY'),
            (sentence(),'AUTHENTICATION_PROTOCOL_ERROR:UNEXPECTED_REPLY'),
        ]
        for reply,expected in cases:
            stream=FakeTls(reply);wire=api._Wire(stream,time.monotonic()+10,2)
            with patch.object(api,'_runtime_material',return_value='v2-SYNTHETIC'),self.assertNoLogs(level='DEBUG'),self.assertRaises(api.ApiSslStop) as error:
                wire.login()
            self.assertEqual(str(error.exception),expected)
            self.assertEqual(stream.sent,sentence('/login','=name=v2-SYNTHETIC','=password=v2-SYNTHETIC'))

    def test_authenticated_read_permission_failure_separate_from_login(self):
        from app.integrations.cebeci_access import ReadIntent
        wire=api._Wire(FakeTls(sentence('!trap','=message=not enough permissions (9)')),time.monotonic()+10,2)
        with self.assertRaisesRegex(api.ApiSslStop,'^DEVICE_READ_REJECTED:TRAP:PERMISSION_DENIED:MESSAGE_CODE_9:CATEGORY_NONE$'):
            wire.read(ReadIntent(menu='/system/identity',properties=('name',)))
