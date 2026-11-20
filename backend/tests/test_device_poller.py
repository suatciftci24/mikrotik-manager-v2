import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from app.schemas.device_inventory import RouterObservation
from app.services.device_poller import OBSERVATION_NAME, poll, preflight


def observation(identity):
    stamp = datetime.now(timezone.utc)
    return RouterObservation(id='device-fixture', identity=identity, observed_at=stamp, last_success_at=stamp, connection='ONLINE')


class DevicePollerTests(TestCase):
    def test_cadence_owner_only_atomic_replace_and_previous(self):
        first, second = observation('first'), observation('second')
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            snapshot = directory / OBSERVATION_NAME
            sample = Mock(side_effect=[first,second])
            stop = Mock()
            stop.is_set.return_value = False
            count = 0
            def wait(seconds):
                nonlocal count
                count += 1
                self.assertEqual(seconds, 58)
                self.assertEqual(json.loads(snapshot.read_text())['routers'][0]['identity'], ('first','second')[count-1])
                self.assertEqual(snapshot.stat().st_mode & 0o777,0o600)
                self.assertEqual(len(list(directory.glob('.device-inventory-*'))),0)
                return count == 2
            stop.wait.side_effect = wait
            poll(sample,directory,stop,clock=iter([0,2,60,62]).__next__)
            self.assertIsNone(sample.call_args_list[0].kwargs['previous'])
            self.assertEqual(sample.call_args_list[1].kwargs['previous'],first)

    def test_failed_replace_preserves_last_snapshot_and_leaves_no_temp_file(self):
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            snapshot=directory/OBSERVATION_NAME
            snapshot.write_text('previous snapshot')
            stop=Mock()
            stop.is_set.return_value=False
            with patch('app.services.device_poller.os.replace',side_effect=OSError()), self.assertRaises(OSError):
                poll(Mock(return_value=observation('new')),directory,stop)
            self.assertEqual(snapshot.read_text(),'previous snapshot')
            self.assertEqual(list(directory.glob('.device-inventory-*')),[])

    def test_previous_profile_cannot_enable_poller(self):
        base={'V2_DEPLOYMENT_PROFILE':'v26-isolated-acceptance'}
        self.assertEqual(preflight(base),'BLOCKED: V26_CEBECI_ACCESS_DISABLED')
        self.assertEqual(preflight({**base,'V2_V26_CEBECI_READ_ENABLED':'true'}),'BLOCKED: V26_CEBECI_CAPABILITY_REJECTED')
        self.assertEqual(preflight({'V2_DEPLOYMENT_PROFILE':'cebeci-vds'}),'BLOCKED: V26_ACCEPTANCE_PROFILE_REQUIRED')

    def test_second_poller_cannot_sample(self):
        import fcntl
        from app.services.device_poller import LOCK_NAME
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            path=directory/LOCK_NAME
            path.touch(mode=0o600)
            with path.open('rb') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                sample=Mock()
                with self.assertRaises(BlockingIOError):
                    poll(sample,directory,Mock())
                sample.assert_not_called()
