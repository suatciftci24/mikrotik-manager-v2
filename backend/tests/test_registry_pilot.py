"""Pilot contract with synthetic wire/storage; never opens device sockets."""
import unittest
from unittest.mock import patch
from dataclasses import replace
from uuid import uuid4
from pydantic import ValidationError
from app.adapters.router_api_ssl import Target,ConnectionPolicy
from app.adapters.cebeci_api_ssl import ApiSslStop
from app.schemas.router_registry import CebeciPilotCandidate,RouterCandidate,RecheckRouter
from app.schemas.router_readonly import ReadOnlySnapshot
from backend.tests.test_router_api_ssl import RouterTransportTests
from backend.tests.test_cebeci_api_ssl import sentence
from backend.tests.test_router_registry import RegistryTests
from app.services import cebeci_registry


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
  self.tls.data=(sentence('!done')+sentence('!re','=name=CEBECI_TOWERS')+sentence('!done')+sentence('!re','=board-name=RB3011UiAS','=version=6.49.19','=cpu-load=2','=total-memory=100','=free-memory=50','=uptime=1d')+sentence('!done')+sentence('!done')+sentence('!done')+sentence('!re','=.id=*1','=service=pppoe','=disabled=false',*extra)+sentence('!done')+sentence('!done'))
 def test_pilot_fixed_reads_minimal_fields_and_strict_snapshot(self):
  self.wire();result=self.client.read_snapshot(self.target,self.credentials,self.policy)
  self.assertEqual(ReadOnlySnapshot.model_validate(result).pppoe_count,1)
  self.assertIn(sentence('/ppp/secret/print','=.proplist=.id,service,disabled'),self.tls.sent)
  self.assertIn(sentence('/ip/hotspot/user/print','=.proplist=.id,disabled'),self.tls.sent)
  self.assertNotIn(b'/set',self.tls.sent);self.assertNotIn(b'/add',self.tls.sent)
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

class PilotRegistryTests(RegistryTests):
 def setUp(self):
  super().setUp();self.policy=ConnectionPolicy(True,'10.250.0.1',('10.250.0.19/32',))
  self.client.probe.return_value={k:snapshot()[k] for k in ('identity','model','routeros_version')}
 def pilot(self):
  payload=CebeciPilotCandidate(request_id=uuid4(),confirmed_read_only=True)
  command=RouterCandidate(request_id=payload.request_id,name=payload.name,management_address='10.250.0.19',username='v2-cebeci-ro',password='SYNTHETIC_PASSWORD_CANARY',ca_pem='SYNTHETIC_PUBLIC_CA',leaf_sha256='a'*64,expected_identity='CEBECI_TOWERS',expected_model='RB3011UiAS',expected_version='6.49.19',confirmed_read_only=True)
  with patch.object(cebeci_registry,'candidate',return_value=command):proof=self.registry.verify_pilot(payload,'actor')
  return payload,proof
 def test_pilot_save_duplicate_and_read_replay_failure_keep_snapshot(self):
  payload,proof=self.pilot();item=self.registry.register(self.command(proof),'actor')['item'];self.assertEqual(item['pilot_kind'],'CEBECI_TOWERS')
  with self.assertRaises(Exception):self.registry.verify_pilot(CebeciPilotCandidate(request_id=uuid4(),confirmed_read_only=True),'actor')
  self.client.read_snapshot.return_value=snapshot()
  request=RecheckRouter(request_id=uuid4(),expected_revision=item['revision'],confirmed_read_only=True)
  result=self.registry.read_details(item['id'],request,'actor');self.assertEqual(result['state'],'SAVED')
  self.assertEqual(self.registry.read_details(item['id'],request,'actor'),result);self.client.read_snapshot.assert_called_once()
  self.client.read_snapshot.side_effect=ApiSslStop('CONNECTION_TIMEOUT')
  failed=self.registry.read_details(item['id'],RecheckRouter(request_id=uuid4(),expected_revision=result['item']['revision'],confirmed_read_only=True),'actor')
  self.assertEqual(failed['state'],'FAILED');self.assertNotIn('SYNTHETIC_PASSWORD_CANARY',str(failed))
  with self.sessions() as session:
   from app.models.router_registry import RegisteredRouter
   saved=session.get(RegisteredRouter,item['id']);self.assertEqual(saved.metadata_snapshot['read_snapshot']['cpu_percent'],2);self.assertEqual(saved.last_error,'CONNECTION_TIMEOUT')
 def test_failed_pilot_cannot_save(self):
  self.client.probe.side_effect=ApiSslStop('TLS_VERIFICATION_FAILED');_,proof=self.pilot();self.assertEqual(proof['state'],'FAILED')
  with self.assertRaises(Exception):self.registry.register(self.command(proof),'actor')

class PilotPayloadTests(unittest.TestCase):
 def test_fixed_public_reference_and_name_validation(self):
  for fields in ({'password':'BAD'},{'management_address':'10.0.0.1'},{'name':'  '},{'name':'x\ny'},{'confirmed_read_only':1}):
   with self.assertRaises(ValidationError):CebeciPilotCandidate.model_validate(dict(request_id=uuid4(),confirmed_read_only=True)|fields)
 def test_disabled_policy_does_not_read_private_files(self):
  with patch.object(cebeci_registry,'_read_pilot_file') as reader:
   with self.assertRaises(ApiSslStop):cebeci_registry.candidate(CebeciPilotCandidate(request_id=uuid4(),confirmed_read_only=True),ConnectionPolicy())
   reader.assert_not_called()

def load_tests(loader,tests,pattern):
 suite=unittest.TestSuite()
 for cls in (PilotWireTests,PilotRegistryTests,PilotPayloadTests):
  for name in cls.__dict__:
   if name.startswith('test_'):suite.addTest(cls(name))
 return suite
