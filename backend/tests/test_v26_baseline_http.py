"""Offline regression for lost pre-attempt HTTPError details and read-only diagnosis."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from contextlib import redirect_stdout
from types import SimpleNamespace
from urllib.error import HTTPError
import unittest
from unittest.mock import Mock,patch

from backend.tests import test_v26_central_development as fixtures


class BaselineHTTP(unittest.TestCase):
    def test_each_pre_attempt_endpoint_reports_exact_stage_url_status_without_runtime_changes(self):
        failures=[('/api/ready',404,'BASELINE_API_READY'),('/api/v1/auth/login',401,'BASELINE_ADMIN_LOGIN'),
                  ('/api/v1/auth/me',403,'BASELINE_ADMIN_ME'),('/api/v1/auth/logout',503,'BASELINE_ADMIN_LOGOUT')]
        for endpoint,status,stage in failures:
            remote=fixtures.CentralDevelopment().remote();original=remote.L['request']
            def open_request(req,timeout):
                path=req.full_url.removeprefix(remote.ORIGIN)
                if path==endpoint:
                    raise HTTPError('https://private.invalid/?token=secret',status,'secret',{},io.BytesIO(b'private row data'))
                data=dict(service='mikrotik-manager-v2',runtime_profile='v26-isolated-acceptance',api_version='v1',api_port=18996) if path=='/api/ready' else dict(id=1,role_code='ADMIN')
                response=Mock(status=200,headers={'Content-Type':'application/json'})
                response.read.return_value=json.dumps(data).encode()
                response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
                return response
            opener=SimpleNamespace(open=open_request)
            output=io.StringIO()
            with self.subTest(endpoint=endpoint),tempfile.TemporaryDirectory() as temp, \
                 patch.multiple(remote,ACTION='baseline',ROOT=Path(temp)/'absent'), \
                 patch.object(remote,'git',return_value=remote.BASELINE),patch.object(remote,'db_identity',return_value='verified'), \
                 patch.object(remote,'setup') as setup,patch.object(remote,'run') as command, \
                 patch.dict(remote.L,{'client':lambda:opener,'services':lambda run:[], 'stash_pin':lambda run:('pinned','oid')}), \
                 patch.object(remote.signal,'signal'),redirect_stdout(output):
                remote.protocol()
                report=json.loads(output.getvalue())
                self.assertEqual(report['status'],'BLOCKED');self.assertEqual(report['failed_stage'],stage)
                self.assertEqual(report['http_status'],status);self.assertEqual(report['request_url'],remote.ORIGIN+endpoint)
                self.assertIsNone(report['evidence_root']);self.assertFalse(report['runtime_switch_started'])
                self.assertFalse(report['db_restore_performed']);self.assertFalse(remote.ROOT.exists())
                self.assertNotIn('secret',output.getvalue());self.assertNotIn('private',output.getvalue())
                setup.assert_not_called();command.assert_not_called()
                self.assertIs(remote.L['request'],original)

    def test_diagnostic_url_drops_query_and_unapproved_origins(self):
        remote=fixtures.CentralDevelopment().remote();opener=Mock()
        opener.open.side_effect=HTTPError('https://private.invalid/?secret=token',401,'private',{},io.BytesIO(b'private'))
        with self.assertRaises(remote.D['AcceptanceFailure']) as caught:
            remote.D['request'](opener,remote.ORIGIN,'/api/v1/auth/login?token=secret','BASELINE_ADMIN_LOGIN')
        self.assertEqual(caught.exception.details['request_url'],remote.ORIGIN+'/api/v1/auth/login')
        self.assertNotIn('secret',json.dumps(caught.exception.details))

    def test_office_baseline_only_sends_diagnostic_action_without_apply_or_observation(self):
        spec=importlib.util.spec_from_file_location('office_baseline',fixtures.ROOT/'tools/central-v26-office.py')
        office=importlib.util.module_from_spec(spec);spec.loader.exec_module(office)
        class Sink(io.BytesIO):
            def close(self):pass
        report=dict(status='BASELINE_VERIFIED',mode='BASELINE_ONLY',runtime_switch_started=False)
        channel=SimpleNamespace(stdin=Sink(),stdout=io.BytesIO((json.dumps(report)+'\n').encode()),poll=lambda:0,wait=lambda *a,**kw:0)
        output=io.StringIO()
        with patch.object(office.sys,'argv',['central-v26-office.py','--baseline-only']), \
             patch.object(office,'git',side_effect=lambda *a:'' if a[0]=='status' else 'a'*40), \
             patch.object(office,'source',return_value=''),patch('builtins.input',return_value='fixture'), \
             patch.object(office.getpass,'getpass',return_value='not-a-real-secret'), \
             patch.object(office.subprocess,'Popen',return_value=channel),patch.object(office,'observe') as observe, \
             patch.object(office.subprocess,'check_output') as artifact,redirect_stdout(output):
            self.assertEqual(office.main(),0)
        self.assertIn(b"ACTION = 'baseline'",channel.stdin.getvalue())
        self.assertEqual(json.loads(output.getvalue()),report)
        observe.assert_not_called();artifact.assert_not_called()
