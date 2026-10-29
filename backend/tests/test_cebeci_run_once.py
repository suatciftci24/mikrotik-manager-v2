"""Mocked CLI pilot only; never connects to a device."""
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from backend.tests.test_cebeci_api_ssl import ApiSslTests,ENV,response,sentence
from app.adapters import cebeci_api_ssl as api

class RunOnceTests(TestCase):
    def test_two_queries_one_socket_source_tls_and_close(self):
        helper=ApiSslTests();helper.setUp()
        self.addCleanup(helper.doCleanups)
        raw,tls,context,factory,builder=helper.mocked(response())
        client=api.CebeciApiSslAdapter(helper.user,helper.cfg())
        result=client._read_session(None)
        self.assertEqual(result,({'name':'CEBECI_TOWERS'},{'board-name':'RB3011UiAS','version':'6.49.19'}))
        self.assertEqual(tls.sent,sentence('/login','=name=v2-fixture','=password=SYNTHETIC_SECRET_CANARY')+sentence('/system/identity/print','=.proplist=name')+sentence('/system/resource/print','=.proplist=board-name,version'))
        factory.assert_called_once();raw.connect.assert_called_once_with(('10.250.0.19',8729))
        raw.bind.assert_called_once_with(('10.250.0.1',0))
        context.wrap_socket.assert_called_once_with(raw,server_hostname='10.250.0.19')
        self.assertTrue(tls.closed);raw.close.assert_called_once()

    def test_cli_files_pinned_configuration_and_no_inherited_overrides(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'V2_CEBECI_API_SSL_PASSWORD':'UNTRUSTED','V2_CEBECI_API_SSL_HOST':'OTHER'},clear=True),patch.object(api,'PILOT_RUNTIME_ROOT',Path(directory)/'pilot'),patch.object(api,'_runtime_material',side_effect=lambda kind,limit:{'USERNAME':'v2-cebeci-ro','PASSWORD':'SYNTHETIC','CA_PEM':'PUBLIC_FIXTURE'}[kind]),patch.object(api.CebeciApiSslAdapter,'_read_session',return_value=({'name':'CEBECI_TOWERS'},{'version':'6.49.19'})) as session:
            self.assertEqual(api.run_once(),'PASS CEBECI_TOWERS 6.49.19')
            session.assert_called_once_with(None)
            self.assertNotIn('V2_CEBECI_API_SSL_PASSWORD',os.environ)
            self.assertNotIn('V2_CEBECI_API_SSL_HOST',os.environ)
            self.assertEqual(os.environ['V2_CEBECI_API_SSL_PASSWORD_FILE'],str(Path(directory)/'pilot/secrets/password'))

    def test_missing_secret_or_wrong_account_stops_before_socket(self):
        for material in (api.ApiSslStop('PILOT_RUNTIME_FILE_REJECTED'),'wrong-account'):
            with patch.dict(os.environ,{},clear=True),patch.object(api,'_runtime_material',side_effect=material if isinstance(material,Exception) else None,return_value=material),patch.object(api.socket,'socket') as socket:
                with self.assertRaises(api.ApiSslStop):api.run_once()
                socket.assert_not_called()
