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

    def test_managed_poller_handoff_get_only_with_expiry_and_file_permissions(self):
        import json
        import os
        from types import SimpleNamespace

        from app.adapters import cebeci_observer as observer
        from app.schemas.device_inventory import Account
        from app.services import device_inventory, device_poller

        stamp = datetime.now(timezone.utc) - timedelta(seconds=1)
        expiry = stamp + timedelta(minutes=15)
        sample = RouterObservation(
            id=observer.ROUTER_ID, identity=observer.IDENTITY, model=observer.MODEL,
            routeros_version=observer.VERSION, observed_at=stamp, last_success_at=stamp,
            connection='ONLINE', accounts_complete=True,
            accounts=[Account(username=f'fixture-{index}') for index in range(123)])
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[current_demo_user] = lambda: {
            'is_demo': True, 'role_code': 'ADMIN', 'can_manage_users': True}
        client = TestClient(app)
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.return_value = True

        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            directory.chmod(0o750)
            snapshot = directory / device_poller.OBSERVATION_NAME
            device_poller.poll(Mock(return_value=sample), directory, stop,
                               clock=lambda: 0, authorize_snapshot=lambda: expiry)
            stop.wait.assert_called_once_with(60)
            self.assertEqual(snapshot.stat().st_mode & 0o777, 0o640)
            contents = snapshot.read_bytes()
            uid, gid = os.geteuid(), os.getegid()
            owner, group = uid or 1200, gid or 1200
            fstat = os.fstat

            def snapshot_stat(fd):
                info = fstat(fd)
                # Root test runners still model the non-root owner and reader group.
                return SimpleNamespace(st_mode=info.st_mode, st_size=info.st_size,
                    st_nlink=info.st_nlink, st_uid=info.st_uid or owner, st_gid=info.st_gid or group)

            with patch.object(device_inventory, 'MANAGED_DIR', directory), \
                 patch.object(device_inventory.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=owner)), \
                 patch.object(device_inventory.grp, 'getgrnam', return_value=SimpleNamespace(gr_gid=group)), \
                 patch.object(device_inventory.os, 'geteuid', return_value=owner+1), \
                 patch.object(device_inventory.os, 'fstat', side_effect=snapshot_stat), \
                 patch.dict(os.environ, {'V2_DEVICE_INVENTORY_MODE':'cebeci-systemd',
                                         'V2_DEVICE_INVENTORY_FILE':''}):
                response = client.get('/device-inventory')
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload['authorization_expires_at'], expiry.isoformat())
                row, = payload['routers']
                self.assertEqual((row['connection'], row['identity'], row['wan_status'],
                                  len(row['accounts']), row['accounts_complete']),
                                 ('ONLINE', observer.IDENTITY, 'UNKNOWN', 123, True))
                self.assertEqual(client.request('PATCH', '/device-inventory', json={'enabled': False}).status_code, 405)

                with patch.dict(os.environ, {'V2_DEVICE_INVENTORY_FILE':str(snapshot)}):
                    self.assertEqual(client.get('/device-inventory').status_code, 503)
                snapshot.chmod(0o660)
                self.assertEqual(client.get('/device-inventory').status_code, 503)
                snapshot.chmod(0o640)
                expired = json.loads(contents)
                expired['authorized_until'] = stamp.isoformat()
                snapshot.write_text(json.dumps(expired))
                self.assertEqual(client.get('/device-inventory').json()['routers'], [])
                snapshot.unlink()
                self.assertEqual(client.get('/device-inventory').json()['routers'], [])
                snapshot.symlink_to(directory / device_poller.LOCK_NAME)
                self.assertEqual(client.get('/device-inventory').status_code, 503)

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
