"""Synthetic wire acceptance; never opens a real socket or database."""
from dataclasses import replace
from unittest import TestCase
from app.adapters import router_api_ssl as transport
from app.adapters.router_readonly import DETAIL_FIELDS
from app.schemas.router_readonly import ReadOnlySnapshot
from backend.tests import test_router_api_ssl as generic_transport
from backend.tests.test_cebeci_api_ssl import sentence

class CebeciTelemetryTests(TestCase):
    def setUp(self):
        generic_transport.RouterTransportTests.setUp(self)
        self.target=replace(self.target,address='10.250.0.19',expected_identity='CEBECI_TOWERS',expected_model='RB3011UiAS',expected_version='6.49.19')
        self.policy=transport.ConnectionPolicy(True,'10.250.0.1',('10.250.0.19/32',))
        self.credentials=('v2-cebeci-ro','SYNTHETIC_PASSWORD_CANARY')
        self.tls.peer=('10.250.0.19',8729);self.tls.local=('10.250.0.1',54321);self.tls.san=(('IP Address','10.250.0.19'),)

    def load(self,route_count=1,address='192.0.2.5/24',extra=None):
        self.tls.sent=b''
        resource=dict(zip(('board-name','version','cpu-load','total-memory','free-memory','uptime'),('RB3011UiAS','6.49.19','5','1000','600','2d')))
        groups={
          '/interface':[{'.id':'*1','name':'ether1','type':'ether','disabled':'false','running':'true'}],
          '/ip/route':[{'dst-address':'0.0.0.0/0','gateway':'192.0.2.1','active':'true','disabled':'false','gateway-status':'192.0.2.1 reachable via ether1'}]*route_count,
          '/ip/address':[{'address':address,'interface':'ether1','disabled':'false'}],
          '/ppp/active':[{'.id':'*2','service':'pppoe'},{'.id':'*3','service':'pptp'}],
          '/ip/hotspot/active':[{'.id':'*4'}],
          '/ppp/secret':[{'.id':'*5','service':'any','disabled':'false'}],
          '/ip/hotspot/user':[],
        }
        if extra:groups['/ppp/active'][0].update(extra)
        def row(value):return sentence('!re',*('='+k+'='+v for k,v in value.items()))
        self.tls.data=sentence('!done')+row({'name':'CEBECI_TOWERS'})+sentence('!done')+row(resource)+sentence('!done')
        for menu in DETAIL_FIELDS:self.tls.data+=b''.join(row(r) for r in groups[menu])+sentence('!done')

    def test_single_tls_session_fixed_reads_and_public_snapshot(self):
        self.load()
        result=ReadOnlySnapshot.model_validate(self.client.read_snapshot(self.target,self.credentials,self.policy))
        self.assertEqual(str(result.wan_ip),'192.0.2.5/24');self.assertEqual(result.wan_interface,'ether1')
        self.assertEqual(result.pppoe_active_count,1);self.assertEqual(result.hotspot_active_count,1)
        self.assertIsNone(result.pppoe_count);self.assertFalse(result.is_demo)
        self.assertNotIn(self.credentials[1],result.model_dump_json())
        self.raw.connect.assert_called_once();self.assertTrue(self.tls.closed)
        for menu,fields in DETAIL_FIELDS.items():
            self.assertIn(sentence(menu+'/print','=.proplist='+','.join(fields)),self.tls.sent)
        self.assertNotIn(b'=password,',self.tls.sent)

    def test_ambiguous_wan_is_unknown_and_invalid_or_secret_reply_stops(self):
        self.load(route_count=2)
        result=self.client.read_snapshot(self.target,self.credentials,self.policy)
        self.assertIsNone(result['wan_ip']);self.assertIsNone(result['wan_interface'])
        for options in ({'address':'invalid'},{'extra':{'password':'CANARY'}}):
            self.load(**options)
            with self.assertRaises(transport.ApiSslStop):self.client.read_snapshot(self.target,self.credentials,self.policy)
            self.assertTrue(self.tls.closed)

    def test_other_target_account_source_or_disabled_gate_never_opens_socket(self):
        for target,credentials,policy in (
            (replace(self.target,address='10.250.0.18'),self.credentials,self.policy),
            (self.target,('webpanel',self.credentials[1]),self.policy),
            (self.target,self.credentials,replace(self.policy,source_ip='10.250.0.2')),
            (self.target,self.credentials,replace(self.policy,enabled=False)),
        ):
            with self.assertRaises(transport.ApiSslStop):self.client.read_snapshot(target,credentials,policy)
        transport.socket.socket.assert_not_called()
