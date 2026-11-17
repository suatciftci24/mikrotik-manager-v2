"""Pilot contract with synthetic wire/storage; never opens device sockets."""
import unittest
from dataclasses import replace
from app.adapters.router_api_ssl import ConnectionPolicy
from app.adapters.cebeci_api_ssl import ApiSslStop
from app.schemas.router_readonly import ReadOnlySnapshot
from backend.tests.test_router_api_ssl import RouterTransportTests
from backend.tests.router_tls_fixtures import sentence


def snapshot():
 return dict(identity='CEBECI_TOWERS',model='RB3011UiAS',routeros_version='6.49.19',cpu_percent=2,memory_percent=50,uptime='1d',captured_at='2026-10-29T12:00:00Z',interfaces=[],default_routes=[],pppoe_count=0,pppoe_explicit_count=0,ppp_any_count=0,hotspot_count=0)

class PilotWireTests(RouterTransportTests):
 def setUp(self):
  super().setUp()
  self.target=replace(self.target,address='10.250.0.19',expected_identity='CEBECI_TOWERS',expected_model='RB3011UiAS',expected_version='6.49.19')
  self.policy=ConnectionPolicy(True,'10.250.0.1',('10.250.0.19/32',))
  self.credentials=('v2-cebeci-ro','SYNTHETIC_PASSWORD_CANARY')
  self.tls.peer=('10.250.0.19',8729);self.tls.local=('10.250.0.1',54321);self.tls.san=(('IP Address','10.250.0.19'),)
 def wire(self,extra=()):
  self.tls.data=(sentence('!done')+sentence('!re','=name=CEBECI_TOWERS')+sentence('!done')+sentence('!re','=board-name=RB3011UiAS','=version=6.49.19','=cpu-load=2','=total-memory=100','=free-memory=50','=uptime=1d')+sentence('!done')+sentence('!done')*5+sentence('!re','=.id=*1','=service=pppoe','=disabled=false',*extra)+sentence('!done')+sentence('!done'))
 def test_pilot_fixed_reads_minimal_fields_and_strict_snapshot(self):
  self.wire();result=self.client.read_snapshot(self.target,self.credentials,self.policy)
  self.assertEqual(ReadOnlySnapshot.model_validate(result).pppoe_count,1)
  self.assertIn(sentence('/ppp/secret/print','=.proplist=.id,service,disabled'),self.tls.sent)
  self.assertIn(sentence('/ip/hotspot/user/print','=.proplist=.id,disabled'),self.tls.sent)
  from app.adapters.router_readonly import DETAIL_FIELDS
  commands=[frame[frame.index(b'/'):].split(b'=',1)[0] for frame in self.tls.sent.split(b'\0') if b'/' in frame]
  self.assertEqual(len(commands),3+len(DETAIL_FIELDS))
  for menu in DETAIL_FIELDS:self.assertIn(sentence(menu+'/print','=.proplist='+','.join(DETAIL_FIELDS[menu])),self.tls.sent)
  self.assertNotIn('SYNTHETIC_PASSWORD_CANARY',str(result));self.assertTrue(self.tls.closed)
 def test_pilot_rejects_unrequested_sensitive_field_and_wrong_target(self):
  self.wire(('=password=CANARY',))
  with self.assertRaisesRegex(ApiSslStop,'UNEXPECTED_RESPONSE_FIELD'):self.client.read_snapshot(self.target,self.credentials,self.policy)
  self.raw.reset_mock()
  with self.assertRaisesRegex(ApiSslStop,'PILOT_SCOPE_MISMATCH'):self.client.read_snapshot(replace(self.target,address='10.250.0.20'),self.credentials,self.policy)
  self.raw.connect.assert_not_called()
 def test_pilot_pin_failure_prevents_login(self):
  self.tls.der=b'bad'
  with self.assertRaisesRegex(ApiSslStop,'CERTIFICATE_PIN_MISMATCH'):self.client.read_snapshot(self.target,self.credentials,self.policy)
  self.assertEqual(self.tls.sent,b'')


def load_tests(loader, tests, pattern):
 return unittest.TestSuite(PilotWireTests(name) for name in PilotWireTests.__dict__ if name.startswith("test_"))
