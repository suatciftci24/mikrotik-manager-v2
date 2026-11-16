"""Offline browser delivery contract: bytes alone cannot prove executable static delivery."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


policy=load('delivery_policy','tools/v26_central_policy.py')
diag=load('delivery_diagnostics','tools/v26_acceptance_diagnostics.py')


class PublicDeliveryContract(unittest.TestCase):
    def profile(self):return dict(instance='12345678-1234-1234-1234-123456789abc',commit='a'*40,database='b'*64)

    def headers(self):
        profile=self.profile()
        return {'Content-Type':'text/html; charset=utf-8',**policy.SECURITY_HEADERS,
                'X-V26-Instance':profile['instance'],'X-V26-Release':profile['commit'],'X-V26-Database':profile['database']}

    def test_missing_or_wrong_security_and_release_headers_fail_closed(self):
        headers=self.headers();self.assertTrue(all(policy.public_header_checks(headers,self.profile()).values()))
        for name in headers:
            for changed in ({key:value for key,value in headers.items() if key!=name},{**headers,name:'invalid'}):
                with self.subTest(header=name):
                    self.assertFalse(all(policy.public_header_checks(changed,self.profile()).values()))

    def test_generated_static_nginx_provides_the_required_security_headers(self):
        text=policy.static_config(policy.APP+'/.local/central/releases/'+'a'*40+'/dist',
                                  policy.APP+'/.local/central/attempt-fixture/static',self.profile())
        for key,value in policy.SECURITY_HEADERS.items():self.assertIn('add_header '+key+' "'+value+'" always;',text)

    def test_mime_types_are_required_even_when_response_bytes_match(self):
        cases=[('/','text/html; charset=utf-8'),('/api/ready','application/json'),
               ('/assets/app.js','text/javascript'),('/assets/app.js','application/javascript'),
               ('/assets/app.css','text/css')]
        for path,mime in cases:
            for content_type in (mime,'application/octet-stream',''):
                with self.subTest(path=path,mime=content_type):
                    response=Mock(status=200,headers={'Content-Type':content_type})
                    response.read.return_value=b'exact expected bytes'
                    response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
                    opener=Mock();opener.open.return_value=response
                    if content_type==mime:self.assertEqual(diag.request(opener,policy.ORIGIN,path,'DELIVERY'),b'exact expected bytes')
                    else:
                        with self.assertRaises(diag.AcceptanceFailure) as caught:diag.request(opener,policy.ORIGIN,path,'DELIVERY')
                        self.assertEqual(caught.exception.details['reason'],'ACCEPTANCE_CONTENT_TYPE_REJECTED')
                        self.assertNotIn('exact expected bytes',json.dumps(caught.exception.details))

    def test_office_observation_rejects_missing_security_header_before_receipt(self):
        office=load('office_delivery','tools/central-v26-office.py')
        # Minimal fixture returns valid login/session; root binding is valid but nosniff is missing.
        headers=self.headers();headers.pop('X-Content-Type-Options')
        legacy='''
class Response:
    status=200
    headers=HEADERS
    def __enter__(self):return self
    def __exit__(self,*args):return False
class Opener:
    def open(self,*args,**kwargs):return Response()
def client():return Opener()
def ready(opener):pass
def admin_check(opener):pass
def request(opener,path,body=None):return b'{"id":1,"role_code":"ADMIN"}'
'''.replace('HEADERS',repr(headers))
        with self.assertRaisesRegex(RuntimeError,'CENTRAL_BROWSER_BINDING_MISMATCH'):
            office.observe(self.profile(),{},'office',legacy,(ROOT/'tools/v26_central_policy.py').read_text())
