#!/usr/bin/env python3
"""Prepared V2-only snapshot refresher. Never invoked by API or app startup."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.adapters.v1_inventory import InventoryFile, MAX_BYTES

ROOT = Path('/srv/mikrotik-manager-v2-fresh-pilot')
ROLE = 'v2_fresh_inventory_ro'


class TransferError(Exception):
    """Only fixed codes may cross the logging boundary."""


def utcnow():
    return datetime.now(timezone.utc)


def read_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
            raise TransferError('invalid_snapshot_file')
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise TransferError('snapshot_too_large')
    return raw, info


def validate(raw, expected, now):
    try:
        # Reject duplicate JSON keys as well as unknown/model-invalid fields.
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError('duplicate key')
                result[key] = value
            return result
        document = json.loads(raw, object_pairs_hook=pairs)
        required = {'id', 'router_id', 'sampled_at', 'cpu_load_percent',
                    'memory_used_percent', 'internet_success'}
        if any(set(sample) != required for sample in document.get('health_samples', [])):
            raise ValueError('incomplete health schema')
        data = InventoryFile.model_validate_json(raw)
        ids = {r.id for r in data.items}
        samples = {s.router_id: s for s in data.health_samples}
        if (len(raw) > MAX_BYTES or len(data.items) != expected or len(ids) != expected
                or any(not r.id.isascii() or not r.id.isdigit() or str(int(r.id)) != r.id or int(r.id) < 1 for r in data.items)
                or len(samples) != len(data.health_samples)
                or len({s.id for s in data.health_samples}) != len(data.health_samples)
                or not set(samples).issubset(ids)
                or any(s.sampled_at > now for s in data.health_samples)
                or any(r.sampled_at and r.sampled_at > now for r in data.items)):
            raise ValueError('invalid identity or time')
        return data
    except (ValueError, TypeError):
        raise TransferError('invalid_snapshot_schema') from None


def candidate(raw, old_raw, expected, now):
    old = validate(old_raw, expected, now)
    new = validate(raw, expected, now)
    if {r.id: r.model_dump() for r in old.items} != {r.id: r.model_dump() for r in new.items}:
        raise TransferError('inventory_changed')
    samples = {s.router_id: s for s in new.health_samples}
    if set(samples) != {r.id for r in new.items}:
        raise TransferError('missing_health_sample')
    for previous in old.health_samples:
        latest = samples[previous.router_id]
        if (latest.sampled_at < previous.sampled_at or int(latest.id) < int(previous.id)
                or (latest.id == previous.id and latest != previous)):
            raise TransferError('health_regression')
    # Source timestamps are preserved. Transfer time is never a measurement time.
    return new.model_dump_json().encode()


def fetch():
    sql = Path(__file__).with_name('health-export.sql').read_text()
    sql = sql.replace('BEGIN READ ONLY;',
                      'BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n'
                      f'SET LOCAL ROLE {ROLE};\nSET LOCAL lock_timeout = \'2s\';', 1)
    # Fixed local socket, database and existing role. No credentials, TCP, grants,
    # fallback identity or V1 code/config imports. SET ROLE must succeed first.
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PGCONNECT_TIMEOUT': '5'}
    try:
        result = subprocess.run(
            ['/usr/sbin/runuser', '-u', 'postgres', '--', '/usr/bin/psql',
             '-XAtq', '-v', 'ON_ERROR_STOP=1', '-h', '/var/run/postgresql',
             '-p', '5432', '-d', 'mikrotik_manager'],
            input=sql.encode(), capture_output=True, timeout=20, env=env)
        if result.returncode or len(result.stdout) > MAX_BYTES:
            raise TransferError('source_read_failed')
        return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        raise TransferError('source_read_failed') from None


def atomic_write(path, raw, info=None):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            if info:
                os.fchown(stream.fileno(), info.st_uid, info.st_gid)
                os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode))
            else:
                os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def emit(report):
    print(json.dumps(report, sort_keys=True), flush=True)


def refresh(snapshot, status, lock, expected=9, reader=fetch):
    if len({snapshot, status, lock}) != 3 or not all(p.is_absolute() for p in (snapshot, status, lock)):
        emit({'result': 'error', 'error_code': 'invalid_paths'})
        return 1
    try:
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'rb') as guard:
            if not stat.S_ISREG(os.fstat(guard.fileno()).st_mode):
                raise TransferError('invalid_lock')
            try:
                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                emit({'attempted_at': utcnow().isoformat(), 'result': 'skipped', 'error_code': 'transfer_busy'})
                return 0
            report = {'attempted_at': utcnow().isoformat(), 'last_success_at': None}
            try:
                previous, _ = read_file(status)
                previous = json.loads(previous)
                # Do not copy arbitrary persisted content into journal/status.
                value = previous.get('last_success_at')
                if value and datetime.fromisoformat(value).tzinfo:
                    report['last_success_at'] = datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
            except (OSError, ValueError, TypeError, AttributeError, TransferError):
                pass
            try:
                old, info = read_file(snapshot)
                raw = candidate(reader(), old, expected, utcnow())
                atomic_write(snapshot, raw, info)
                report.update(result='success', error_code=None, last_success_at=utcnow().isoformat())
            except TransferError as error:
                report.update(result='error', error_code=str(error))
            except Exception:
                report.update(result='error', error_code='transfer_failed')
            try:
                atomic_write(status, json.dumps(report).encode())
            except Exception:
                emit({'attempted_at': report['attempted_at'], 'result': 'error', 'error_code': 'status_write_failed'})
                return 1
            emit(report)
            return 0 if report['result'] == 'success' else 1
    except Exception:
        emit({'attempted_at': utcnow().isoformat(), 'result': 'error', 'error_code': 'lock_failed'})
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'config/v1-inventory.json')
    parser.add_argument('--status', type=Path, default=ROOT / 'config/health-transfer-status.json')
    parser.add_argument('--lock', type=Path, default=Path('/run/mikrotik-v2-health-transfer/transfer.lock'))
    args = parser.parse_args()
    return refresh(args.snapshot, args.status, args.lock)


if __name__ == '__main__':
    raise SystemExit(main())
