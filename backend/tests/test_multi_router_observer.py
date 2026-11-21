"""Isolated grant, snapshot, scheduler, and API-SSL coverage for registry routers."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest import TestCase
from unittest.mock import Mock, patch

from app.adapters.cebeci_api_ssl import ApiSslStop
from app.router_observer import make_sampler
from app.schemas.device_inventory import Account, DeviceInventory, RouterObservation
from app.services import device_inventory, device_poller
from app.services import router_observation_grants as grants


def document(number):
    return grants.GrantDocument.model_validate({
        'grant': {
            'scope': 'ROUTEROS_READ_ONLY',
            'router_id': f'registered-00000000-0000-4000-8000-{number:012}',
            'grant_id': f'{number:032}',
            'name': f'Fixture {number}', 'identity': f'LAB-{number}', 'model': 'LAB-MODEL',
            'management_address': f'10.77.0.{number}', 'source_ip': '10.77.0.1',
            'port': 8729, 'configuration_revision': 1, 'leaf_sha256': 'a' * 64,
            'routeros_version': '7.20.1', 'credential_ref': f'10000000-0000-4000-8000-{number:012}',
            'read_only_username': f'v2-lab-{number}', 'wan_interface': 'wan',
        },
        'trust': {'ca_pem': 'SYNTHETIC_PUBLIC_CA'},
    })


def observation(doc, *, online=True):
    grant = doc.grant
    stamp = datetime.now(timezone.utc) - timedelta(seconds=1)
    return RouterObservation(id='device-' + grant.router_id, identity=grant.identity, model=grant.model,
        routeros_version=grant.routeros_version, observed_at=stamp, last_success_at=stamp if online else None,
        connection='ONLINE' if online else 'OFFLINE', error=None if online else 'UNREACHABLE',
        accounts=[Account(username='same-name')] if online else None)


def snapshot(doc, *, online=True):
    return DeviceInventory(source='ROUTEROS_READ_ONLY', grant_id=doc.grant.grant_id,
                           routers=[observation(doc, online=online)])


class MultiRouterObserverTests(TestCase):
    def setUp(self):
        self.a, self.b = document(2), document(3)

    def test_multi_inventory_rejects_old_generation_and_isolates_bad_snapshot(self):
        active = {doc.grant.router_id: doc for doc in (self.a, self.b)}
        data = {grants.RUN / (grants.PREFIX + doc.grant.router_id): snapshot(doc) for doc in (self.a, self.b)}
        a_path = grants.RUN / (grants.PREFIX + self.a.grant.router_id)

        def read(path=None, *_):
            result = data.get(path)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(grants, 'documents', side_effect=lambda: list(active.values())), \
             patch.object(grants, 'read_document', side_effect=active.__getitem__), \
             patch.object(device_inventory, '_managed_snapshot', side_effect=read), \
             patch.dict('os.environ', {'V2_DEVICE_INVENTORY_MODE': 'multi-router-systemd',
                                       'V2_DEVICE_INVENTORY_FILE': ''}):
            rows = device_inventory.read_inventory()['routers']
            self.assertEqual([r['accounts'][0]['username'] for r in rows], ['same-name', 'same-name'])
            self.assertNotEqual(rows[0]['id'], rows[1]['id'])
            self.assertNotIn(str(self.a.grant.credential_ref), str(rows))
            data[a_path] = snapshot(self.a, online=False)
            self.assertEqual([r['connection'] for r in device_inventory.read_inventory()['routers']],
                             ['OFFLINE', 'ONLINE'])
            data[a_path] = OSError()
            self.assertEqual([r['connection'] for r in device_inventory.read_inventory()['routers']],
                             ['UNKNOWN', 'ONLINE'])
            del active[self.a.grant.router_id]
            self.assertEqual([r['identity'] for r in device_inventory.read_inventory()['routers']], ['LAB-3'])
            active[self.a.grant.router_id] = self.a.model_copy(update={
                'grant': self.a.grant.model_copy(update={'grant_id': '0' * 32}),
            })
            data[a_path] = snapshot(self.a)
            restored = next(r for r in device_inventory.read_inventory()['routers'] if r['identity'] == 'LAB-2')
            self.assertIsNone(restored['accounts'])

    def test_revocation_stops_before_vault_or_publication(self):
        client = Mock()
        vault = Mock(return_value=None)
        with patch.object(grants, 'read_document', side_effect=FileNotFoundError):
            sample = make_sampler(self.a, vault, client)
            with self.assertRaisesRegex(ApiSslStop, 'OBSERVATION_GRANT_REVOKED'):
                sample(previous=None)
        vault.read.assert_not_called()
        client.read_inventory_observation.assert_not_called()
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            directory.chmod(0o750)
            check = Mock(side_effect=[self.a.grant.grant_id, ApiSslStop('OBSERVATION_GRANT_REVOKED')])
            with self.assertRaisesRegex(ApiSslStop, 'OBSERVATION_GRANT_REVOKED'):
                device_poller.poll(Mock(return_value=observation(self.a)), directory,
                                   Event(), authorize_grant=check)
            self.assertFalse((directory / device_poller.OBSERVATION_NAME).exists())

    def test_independent_workers_do_not_wait_for_slow_peer(self):
        entered, release, done = Event(), Event(), Event()
        errors = []

        def run(doc, directory, slow=False):
            stop = Mock()
            stop.is_set.return_value = False

            def wait(seconds):
                self.assertEqual(seconds, 60)
                if not slow:
                    done.set()
                return True

            def sample(*, previous):
                if slow:
                    entered.set()
                    if not release.wait(5):
                        raise AssertionError('fixture was not released')
                return observation(doc, online=not slow)

            stop.wait.side_effect = wait
            try:
                device_poller.poll(sample, directory, stop, clock=lambda: 0,
                                   authorize_grant=lambda: doc.grant.grant_id)
            except Exception as error:
                errors.append(error)

        with TemporaryDirectory() as tmp:
            directories = [Path(tmp) / str(i) for i in (1, 2)]
            for directory in directories:
                directory.mkdir(mode=0o750)
            a = Thread(target=run, args=(self.a, directories[0], True))
            b = Thread(target=run, args=(self.b, directories[1]))
            a.start()
            try:
                self.assertTrue(entered.wait(2))
                b.start()
                try:
                    self.assertTrue(done.wait(2))
                    result = DeviceInventory.model_validate_json(
                        (directories[1] / device_poller.OBSERVATION_NAME).read_bytes())
                    self.assertEqual(result.routers[0].connection, 'ONLINE')
                finally:
                    b.join(3)
            finally:
                release.set()
                a.join(3)
            self.assertFalse(a.is_alive() or b.is_alive())
            self.assertEqual(errors, [])

    def test_operator_approval_replacement_and_revocation_change_files_atomically(self):
        import os
        from types import SimpleNamespace
        from app import router_observation_access as access

        doc = self.a
        items = doc.grant.model_dump(mode='json', exclude={
            'scope', 'grant_id', 'credential_ref', 'read_only_username', 'wan_interface'})
        payload = {'router': dict(items, trust=doc.trust.model_dump(), pending_verification=False),
                   'credential_ref': str(doc.grant.credential_ref),
                   'read_only_username': doc.grant.read_only_username,
                   'wan_interface': doc.grant.wan_interface}
        with TemporaryDirectory() as tmp:
            fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY)
            self.addCleanup(os.close, fd)
            real_fstat = os.fstat

            def root_stat(file):
                info = real_fstat(file)
                return SimpleNamespace(st_uid=0, st_gid=info.st_gid, st_mode=info.st_mode,
                                       st_nlink=info.st_nlink, st_size=info.st_size)

            with patch.object(grants.grp, 'getgrnam', return_value=SimpleNamespace(gr_gid=os.getegid())), \
                 patch.object(access.os, 'fchown'), patch.object(grants.os, 'fstat', side_effect=root_stat), \
                 patch.object(access, 'verified_tls_context') as verify:
                access.approve(fd, doc.grant.router_id, payload)
                verify.assert_called_once_with(doc.trust.ca_pem)
                before = grants.read_document(doc.grant.router_id, directory=fd)
                with self.assertRaisesRegex(ValueError, 'OBSERVATION_GRANT_ALREADY_EXISTS'):
                    access.approve(fd, doc.grant.router_id, payload)
                self.assertEqual(grants.read_document(doc.grant.router_id, directory=fd), before)
                access.approve(fd, doc.grant.router_id, payload, replace=True)
                after = grants.read_document(doc.grant.router_id, directory=fd)
                self.assertNotEqual(before.grant.grant_id, after.grant.grant_id)
                access.revoke(fd, doc.grant.router_id)
                access.revoke(fd, doc.grant.router_id)
                with self.assertRaises(FileNotFoundError):
                    grants.read_document(doc.grant.router_id, directory=fd)
            self.assertEqual(os.listdir(fd), [])

    def test_multi_mode_preserves_unexpired_cebeci_pilot(self):
        from app.adapters import cebeci_observer as pilot

        stamp = datetime.now(timezone.utc) - timedelta(seconds=1)
        data = DeviceInventory(source='ROUTEROS_READ_ONLY', authorized_until=stamp + timedelta(hours=1),
            routers=[RouterObservation(id=pilot.ROUTER_ID, identity=pilot.IDENTITY, model=pilot.MODEL,
                routeros_version=pilot.VERSION, observed_at=stamp, last_success_at=stamp, connection='ONLINE')])
        with patch.object(grants, 'documents', return_value=[self.a]), \
             patch.object(grants, 'read_document', return_value=self.a), \
             patch.object(device_inventory, '_managed_snapshot', side_effect=[snapshot(self.a), data]), \
             patch.dict('os.environ', {'V2_DEVICE_INVENTORY_MODE': 'multi-router-systemd',
                                       'V2_DEVICE_INVENTORY_FILE': ''}):
            result = device_inventory.read_inventory()
        self.assertNotIn('authorization_expires_at', result)
        self.assertEqual([row['access'] for row in result['routers']], ['PERSISTENT', 'PILOT'])
        self.assertEqual(result['routers'][1]['authorization_expires_at'], data.authorized_until.isoformat())
