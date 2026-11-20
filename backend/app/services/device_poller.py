"""Operations primitives for a separately authorized V2 observation producer."""
import fcntl
import os
import stat
from pathlib import Path
from time import monotonic
from uuid import uuid4

INTERVAL_SECONDS = 60
OBSERVATION_NAME = 'device-inventory.json'
LOCK_NAME = '.device-inventory.lock'


def _publish(directory, observation):
    from app.schemas.device_inventory import DeviceInventory
    from app.services.device_inventory import MAX_BYTES

    payload = DeviceInventory(source='ROUTEROS_READ_ONLY', routers=[observation]).model_dump_json().encode()
    if len(payload) > MAX_BYTES:
        raise ValueError('POLL_SNAPSHOT_TOO_LARGE')
    temporary = '.device-inventory-' + uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, OBSERVATION_NAME, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def poll(sample, output_dir: Path, stop, *, clock=monotonic):
    """Schedule a trusted sampler. No transport, environment, or credential resolution."""
    if not output_dir.is_absolute() or output_dir.resolve(strict=True) != output_dir:
        raise ValueError('POLL_OUTPUT_DIRECTORY_REJECTED')
    directory = os.open(output_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('POLL_OUTPUT_DIRECTORY_REJECTED')
        lock = os.open(LOCK_NAME, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                       0o600, dir_fd=directory)
        try:
            info = os.fstat(lock)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
                raise ValueError('POLL_LOCK_REJECTED')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            previous = None
            while not stop.is_set():
                started = clock()
                observation = sample(previous=previous)
                _publish(directory, observation)
                previous = observation
                if stop.wait(max(0, INTERVAL_SECONDS-(clock()-started))):
                    break
        finally:
            os.close(lock)
    finally:
        os.close(directory)


def preflight(values):
    from app.core import v26_cebeci
    if not v26_cebeci.in_profile(values):
        return 'BLOCKED: V26_ACCEPTANCE_PROFILE_REQUIRED'
    try:
        v26_cebeci.validate(values)
    except RuntimeError:
        return 'BLOCKED: V26_CEBECI_CAPABILITY_REJECTED'
    if not v26_cebeci.enabled(values):
        return 'BLOCKED: V26_CEBECI_ACCESS_DISABLED'
    return 'BLOCKED: POLL_PRODUCER_NOT_AUTHORIZED_BY_RUNTIME'


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['--preflight']:
        raise SystemExit('Usage: python3 -m app.services.device_poller --preflight')
    print(preflight(os.environ), file=sys.stderr)
    raise SystemExit(1)
