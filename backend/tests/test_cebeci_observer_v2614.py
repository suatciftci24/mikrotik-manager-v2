"""Standalone grant tests. No secrets, router, DB, or network."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch, sentinel

from app.adapters import cebeci_observer as observer
from app.adapters.cebeci_api_ssl import ApiSslStop
from app.adapters.router_api_ssl import ConnectionPolicy, Target


class ObserverTests(TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.approval = dict(scope=observer.SCOPE, expires_at=(self.now+timedelta(minutes=15)).isoformat())
        self.target = Target(observer.ADDRESS, observer.PORT, 'CA fixture', observer.REVIEWED_LEAF_SHA256,
                             observer.IDENTITY, observer.VERSION, observer.MODEL)
        self.policy = ConnectionPolicy(True, observer.SOURCE, (observer.ADDRESS+'/32',), (observer.PORT,))
        env = patch.dict('os.environ', {}, clear=True)
        uid = patch.object(observer.os,'geteuid',return_value=1000)
        for patcher in (env,uid):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_default_closed_and_invalid_expiry_scope_and_legacy_environment(self):
        with patch.object(observer,'_read_pilot_file',side_effect=ApiSslStop('missing')) as read:
            with self.assertRaisesRegex(ApiSslStop,'NOT_AUTHORIZED'):
                observer.make_sampler()
            read.assert_called_once_with(str(observer.ROOT/'approval.json'),4096)
        for options in (dict(expires_at=self.now.isoformat()),dict(expires_at=(self.now+timedelta(days=2)).isoformat()),
                        dict(expires_at='2026-01-01T12:00:00'),dict(scope='OTHER'),dict(host='10.250.0.20')):
            with patch.object(observer,'_read_pilot_file',return_value=json.dumps({**self.approval,**options})):
                with self.assertRaisesRegex(ApiSslStop,'NOT_AUTHORIZED'):
                    observer.authorize(self.now)
        for key,value in [('V2_DEPLOYMENT_PROFILE','v26-isolated-acceptance'),('V2_V26_CEBECI_READ_ENABLED','true'),
                          ('V2_CEBECI_API_SSL_ENABLED','true'),('V2_ROUTER_ONBOARDING_OPERATOR_IDS','someone')]:
            with patch.dict('os.environ',{key:value}),patch.object(observer,'_read_pilot_file') as read:
                with self.assertRaisesRegex(ApiSslStop,'NOT_AUTHORIZED'):
                    observer.authorize(self.now)
                read.assert_not_called()

    def test_exact_scope_only_and_revocation_before_transport(self):
        client = observer.CebeciObserverClient()
        credentials = (observer.USERNAME,'synthetic-fixture')
        with patch.object(observer,'_read_pilot_file',return_value=json.dumps(self.approval)) as file, \
             patch.object(client,'_verified_read',return_value=sentinel.result) as transport:
            for mutation in (dict(address='10.250.0.20'),dict(port=8728),dict(expected_identity='OTHER'),
                             dict(expected_model='OTHER'),dict(expected_version='7.20'),dict(leaf_sha256='0'*64)):
                with self.assertRaisesRegex(ApiSslStop,'SCOPE_REJECTED'):
                    client.read_inventory_observation(replace(self.target,**mutation),credentials,self.policy,
                        router_id=observer.ROUTER_ID,wan_interface=None)
            with self.assertRaisesRegex(ApiSslStop,'SCOPE_REJECTED'):
                client.read_inventory_observation(self.target,credentials,replace(self.policy,source_ip='10.250.0.2'),
                    router_id=observer.ROUTER_ID,wan_interface=None)
            transport.assert_not_called()
            self.assertIs(client.read_inventory_observation(self.target,credentials,self.policy,
                router_id=observer.ROUTER_ID,wan_interface=None),sentinel.result)
            transport.assert_called_once_with(self.target,credentials,self.policy,False,(observer.ROUTER_ID,None))
            file.side_effect = ApiSslStop('revoked')
            with self.assertRaisesRegex(ApiSslStop,'NOT_AUTHORIZED'):
                client.read_inventory_observation(self.target,credentials,self.policy,router_id=observer.ROUTER_ID,wan_interface=None)
            self.assertEqual(transport.call_count,1)

    def test_sampler_passes_previous_and_uses_managed_wan(self):
        files = [json.dumps({**self.approval,'wan_interface':'fixture-wan'}),'synthetic-public-ca','synthetic-password']
        with patch.object(observer,'_read_pilot_file',side_effect=files+[files[0],ApiSslStop('revoked')]), \
             patch('app.services.device_inventory.sample_device',return_value=sentinel.new) as take:
            sample = observer.make_sampler()
            self.assertIs(sample(previous=sentinel.old),sentinel.new)
            self.assertEqual(take.call_args.kwargs,dict(router_id=observer.ROUTER_ID,wan_interface='fixture-wan',previous=sentinel.old))
            with self.assertRaisesRegex(ApiSslStop,'NOT_AUTHORIZED'):
                sample(previous=sentinel.new)
            self.assertEqual(take.call_count,1)

    def test_approved_poll_uses_pinned_tls_read_only_wire_and_private_output(self):
        import hashlib
        import ssl
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import Mock
        from app.adapters import router_api_ssl
        from app.services.device_poller import OBSERVATION_NAME, poll
        from backend.tests.router_tls_fixtures import FakeTls, DER, sentence

        frames = (sentence('!done')
                  + sentence('!re','=name='+observer.IDENTITY) + sentence('!done')
                  + sentence('!re','=board-name='+observer.MODEL,'=version='+observer.VERSION,
                             '=cpu-load=12','=total-memory=100','=free-memory=30','=uptime=1d')
                  + sentence('!done') * 4)
        stream = FakeTls(frames)
        stream.peer = (observer.ADDRESS,observer.PORT)
        stream.local = (observer.SOURCE,55555)
        stream.san = (('IP Address',observer.ADDRESS),)
        context = Mock(verify_mode=ssl.CERT_REQUIRED,check_hostname=True,
                       minimum_version=ssl.TLSVersion.TLSv1_2,hostname_checks_common_name=False)
        context.wrap_socket.return_value = stream
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.return_value = True

        def material(path, limit):
            return {'approval.json':json.dumps(self.approval),'ca.pem':'PUBLIC_CA_FIXTURE',
                    'password':'SYNTHETIC_PASSWORD_CANARY'}[Path(path).name]

        with TemporaryDirectory() as directory, patch.object(observer,'_read_pilot_file',side_effect=material), \
             patch.object(observer,'REVIEWED_LEAF_SHA256',hashlib.sha256(DER).hexdigest()), \
             patch.object(router_api_ssl,'verified_tls_context',return_value=context), \
             patch.object(router_api_ssl.socket,'socket') as socket:
            # Filesystem owner validation uses the actual test user.
            with patch.object(observer.os,'geteuid',return_value=Path(directory).stat().st_uid):
                poll(observer.make_sampler(),Path(directory),stop,clock=lambda:0)
            expected = json.loads((Path(directory)/OBSERVATION_NAME).read_text())['routers'][0]
            self.assertEqual((expected['identity'],expected['cpu_percent']), (observer.IDENTITY,12))
            self.assertNotIn('SYNTHETIC_PASSWORD_CANARY',str(expected))
            socket.return_value.bind.assert_called_once_with((observer.SOURCE,0))
            socket.return_value.connect.assert_called_once_with((observer.ADDRESS,observer.PORT))
            self.assertNotIn(b'/set',stream.sent)
            self.assertNotIn(b'.proplist=password',stream.sent)
            stop.wait.assert_called_once_with(60)
