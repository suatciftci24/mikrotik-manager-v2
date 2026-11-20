"""Device observations exercise framed synthetic replies and file-backed HTTP only."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from time import monotonic

from fastapi import FastAPI
from app.adapters.cebeci_api_ssl import ApiSslStop
from app.adapters.device_inventory import DeviceReadWire
from app.api.v1.device_inventory import router
from app.core.security import current_demo_user
from app.schemas.device_inventory import DeviceInventory, RouterObservation
from backend.tests.test_workspace_operator_access import TestClient



class DeviceInventoryTests(TestCase):
    def test_write_and_unapproved_properties_never_reach_wire(self):
        stream = Mock()
        wire = DeviceReadWire(stream,monotonic()+2,1)
        for words in (('/ppp/secret/set','=disabled=yes'), ('/ppp/secret/print','=.proplist=password'), ('/login',)):
            with self.assertRaisesRegex(ApiSslStop,'READ_SCOPE_REJECTED'):
                wire.send(words)
        stream.sendall.assert_not_called()

    def test_real_source_admin_only_freshness_and_fail_closed(self):
        now=datetime.now(timezone.utc)
        fresh=now-timedelta(seconds=10)
        stale=now-timedelta(minutes=6)
        inv=DeviceInventory(source='ROUTEROS_READ_ONLY', routers=[
            RouterObservation(id='device-fresh',observed_at=fresh,last_success_at=fresh,connection='ONLINE',cpu_percent=12,rx_bytes=2**64-1),
            RouterObservation(id='device-stale',observed_at=stale,last_success_at=stale,connection='ONLINE',cpu_percent=40,accounts=[]),
            RouterObservation(id='device-offline',observed_at=fresh,last_success_at=stale,connection='OFFLINE',error='UNREACHABLE'),
        ])
        app=FastAPI()
        app.include_router(router)
        user={'is_demo':True,'role_code':'ADMIN','can_manage_users':True}
        app.dependency_overrides[current_demo_user]=lambda:user
        client=TestClient(app)
        with TemporaryDirectory() as directory:
            file=Path(directory)/'snapshot.json'
            with patch.dict('os.environ',{'V2_DEVICE_INVENTORY_FILE':''}):
                self.assertEqual(client.get('/device-inventory').json()['routers'],[])
            file.touch(mode=0o600)
            file.write_text(inv.model_dump_json())
            with patch.dict('os.environ',{'V2_DEVICE_INVENTORY_FILE':str(file)}):
                user['can_manage_users']=False
                self.assertEqual(client.get('/device-inventory').status_code,403)
                user['can_manage_users']=True
                response=client.get('/device-inventory')
                self.assertEqual(response.headers['cache-control'],'no-store')
                fresh_row, stale_row, offline_row=response.json()['routers']
                self.assertEqual(fresh_row['rx_bytes'],str(2**64-1))
                self.assertEqual((stale_row['connection'],stale_row['cpu_percent'],stale_row['accounts']),('UNKNOWN',None,None))
                self.assertEqual((offline_row['connection'],offline_row['last_success_at']),('OFFLINE',stale_row['last_success_at']))
                self.assertEqual(client.post('/device-inventory').status_code,405)
                file.write_text(inv.model_dump_json().replace('"source":','"password":"PRIVATE_CANARY","source":'))
                invalid=client.get('/device-inventory')
                self.assertEqual(invalid.status_code,503)
                self.assertNotIn('PRIVATE_CANARY',invalid.text)

    def test_failed_poll_keeps_last_success_and_never_copies_session_or_error_message(self):
        from app.services.device_inventory import sample_device
        from types import SimpleNamespace
        stamp=datetime.now(timezone.utc)-timedelta(minutes=1)
        previous=RouterObservation(id='device-lab',identity='fixture',observed_at=stamp,
            last_success_at=stamp,connection='ONLINE',accounts=[])
        client=Mock()
        for code,status,error in [('CONNECTION_UNREACHABLE','OFFLINE','UNREACHABLE'),
                                  ('CONNECTION_TIMEOUT','UNKNOWN','TIMEOUT'),
                                  ('TLS_VERIFICATION_FAILED','UNKNOWN','TLS'),
                                  ('AUTHENTICATION_REJECTED','UNKNOWN','AUTHORIZATION'),
                                  ('PRIVATE_CANARY','UNKNOWN','INVALID_DATA')]:
            client.reset_mock()
            client.read_inventory_observation.side_effect=ApiSslStop(code)
            result=sample_device(client,SimpleNamespace(expected_identity='fixture'),None,None,
                                 router_id='device-lab',wan_interface=None,previous=previous)
            self.assertEqual((result.connection,result.error,result.last_success_at),(status,error,stamp))
            self.assertIsNone(result.accounts)
            self.assertNotIn('PRIVATE_CANARY',result.model_dump_json())
            client.read_inventory_observation.assert_called_once()
