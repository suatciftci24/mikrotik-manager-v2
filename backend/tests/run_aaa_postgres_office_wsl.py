"""Office WSL only: new isolated cluster or explicit pinned-existing acceptance.

Default provision refuses an existing root. --existing never creates a cluster.
No application wiring, external DB, real identity or provider.
"""
import os
import json
import stat
import time
from contextlib import contextmanager
from pathlib import Path
import platform
import subprocess
import sys
import unittest

from backend.tests import run_aaa_postgres_wsl as provision
from backend.tests.run_v26_http_acceptance_wsl import _isolated_runtime

REPO = Path('/home/suatpc/Codex-Projects/mikrotik-manager-v2')
HOST = 'DESKTOP-VD5T7VG'
PYTHON = REPO / '.venv/bin/python'
EXISTING_CLUSTER_ID = '7707521885424832975'


def office_guard():
    if (Path.cwd() != REPO or Path(__file__).resolve().parents[2] != REPO
            or platform.node() != HOST or not os.environ.get('WSL_DISTRO_NAME')
            or 'microsoft' not in Path('/proc/version').read_text().lower()
            or os.getuid() <= 0 or os.getuid() != os.geteuid()
            or REPO.stat().st_uid != os.getuid()
            or Path(sys.prefix).resolve() != (REPO / '.venv').resolve()):
        raise RuntimeError('OFFICE_WSL_IDENTITY_REJECTED')
    branch = subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    if branch != 'main-guncel':
        raise RuntimeError('OFFICE_BRANCH_REJECTED')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():
        raise RuntimeError('DIRTY_WORKTREE_REJECTED')


def run_bridge(cluster_id):
    # Identity comes from verified new provisioning or the hard-pinned existing
    # Office cluster. No environment/CLI arbitrary cluster ID or DSN override.
    if not isinstance(cluster_id,str) or not cluster_id.isdecimal():
        raise RuntimeError('VERIFIED_CLUSTER_ID_REQUIRED')
    from backend.tests.test_aaa_pg_bridge import PostgresBridgeAcceptance
    class OfficeAcceptance(PostgresBridgeAcceptance):
        expected_cluster_id = cluster_id
        environment_guard = staticmethod(office_guard)
    # Parent opt-in decorator is retained; activate only in this explicit runner.
    if os.environ.get('V2_AAA_EXISTING_PG_TESTS') != '1':
        raise RuntimeError('EXPLICIT_OFFICE_PG_OPT_IN_REQUIRED')
    # The inherited class skip flag was bound at import; the import above must
    # occur only after main's explicit process-local opt-in is installed.
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OfficeAcceptance)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful() or result.testsRun != 11 or result.skipped:
        raise RuntimeError('OFFICE_ELEVEN_PG_TESTS_NOT_PASSED')
    print('PASS: Office isolated AAA PostgreSQL 11 scenarios; not production acceptance')


@contextmanager
def office_runtime():
    # Identity was checked before entering. Preserve the exact WSL marker needed
    # by the second guard, not inherited libpq/loader/connection settings.
    distro = os.environ.get('WSL_DISTRO_NAME')
    if not distro:
        raise RuntimeError('OFFICE_WSL_IDENTITY_REJECTED')
    with _isolated_runtime():
        os.environ['WSL_DISTRO_NAME'] = distro
        os.environ['V2_AAA_EXISTING_PG_TESTS'] = '1'
        yield


def verify_existing_files():
    from backend.tests.v26_disposable_cluster import DisposableClusterGuard
    root = provision.ROOT
    guard = DisposableClusterGuard(root)
    guard(root / 'postgres-test')
    manifest_path = root / 'fixture-manifest.json'
    password_path = root / 'test-password'
    for path in (manifest_path, password_path):
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
                or info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise RuntimeError('EXISTING_PRIVATE_FILE_REJECTED')
    manifest = json.loads(manifest_path.read_text())
    # HOME was a historical provisioner label, NOT host identity evidence.
    # Accept it only for this exact independently pinned Office cluster.
    if (manifest.get('purpose') not in ('HOME_WSL_AAA_FIXTURE', 'OFFICE_WSL_AAA_FIXTURE')
            or (manifest.get('port'),manifest.get('database'),manifest.get('runtime_role'))
                != (55433, provision.DB, provision.ROLE)):
        raise RuntimeError('EXISTING_FIXTURE_MANIFEST_REJECTED')
    for path, key in ((root,'root_identity'),(root/'postgres-test','data_identity')):
        info = path.lstat()
        if (info.st_dev,info.st_ino,info.st_uid) != tuple(manifest.get(key, ())):
            raise RuntimeError('EXISTING_FIXTURE_OWNERSHIP_REJECTED')
    data = root / 'postgres-test'
    socket_dir = root / 'socket'
    info = socket_dir.lstat()
    if (socket_dir.is_symlink() or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise RuntimeError('EXISTING_SOCKET_DIRECTORY_REJECTED')
    log = root / 'postgres.log'
    if os.path.lexists(log):
        info = log.lstat()
        if log.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise RuntimeError('EXISTING_LOG_REJECTED')
    for name in ('standby.signal','recovery.signal'):
        if os.path.lexists(data / name):
            raise RuntimeError('RECOVERY_CLUSTER_REJECTED')
    for name in ('postgresql.conf','postgresql.auto.conf','pg_hba.conf'):
        path = data / name
        if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
            raise RuntimeError('EXISTING_CONFIG_REJECTED')
        # No include indirection into another installation or startup hook.
        for line in path.read_text().splitlines():
            setting = line.strip()
            if setting and not setting.startswith('#') and name != 'pg_hba.conf':
                allowed = {'max_connections','shared_buffers','dynamic_shared_memory_type','max_wal_size','min_wal_size',
                    'log_timezone','datestyle','timezone','lc_messages','lc_monetary','lc_numeric','lc_time','default_text_search_config'}
                if setting.split('=')[0].strip() not in allowed:
                    raise RuntimeError('EXISTING_NONDEFAULT_CONFIG_REJECTED')
            if setting and not setting.startswith('#') and setting.split('=')[0].strip().startswith(
                    ('include','shared_preload_libraries','session_preload_libraries','local_preload_libraries',
                     'primary_conninfo','restore_command','archive_command')):
                raise RuntimeError('EXISTING_CONFIG_INDIRECTION_REJECTED')
    result = subprocess.run([str(provision.PG/'pg_controldata'),str(data)],check=True,
        capture_output=True,text=True,env={**provision.runtime_environment(),'LC_ALL':'C'})
    fields = dict(line.split(':',1) for line in result.stdout.splitlines() if ':' in line)
    if fields.get('Database system identifier','').strip() != EXISTING_CLUSTER_ID:
        raise RuntimeError('EXACT_OFFICE_CLUSTER_REQUIRED')
    return manifest, fields.get('Database cluster state','').strip()


def run_existing():
    manifest, state = verify_existing_files()
    # Adopt only this private, pinned directory; OwnedRoot.__init__ creates a
    # directory and must NEVER be called for an existing cluster.
    owned = object.__new__(provision.OwnedRoot)
    owned.root = provision.ROOT
    owned.identity = tuple(manifest['root_identity'])
    owned.data_identity = tuple(manifest['data_identity'])
    owned.fd = os.open(owned.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    owned.parent_fd = os.open('/tmp', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    owned.process_identity = None
    owned.start_after = None
    owned.pg_stopped = True
    owned.http_running = False
    started = False
    try:
        data = owned.verify_data()
        if state == 'shut down':
            # Refuse an occupied port before starting our existing stopped cluster.
            with provision.socket.socket(provision.socket.AF_INET,provision.socket.SOCK_STREAM) as port:
                port.bind(('127.0.0.1',55433))
            owned.start_after = int(time.time())
            started = True
            owned.pg_stopped = False
            provision.run_tool([str(provision.PG/'pg_ctl'),'-D',str(data),'-l',str(owned.root/'postgres.log'),
                '-o','-h 127.0.0.1 -p 55433 -k '+str(owned.root/'socket')+
                ' -c log_statement=none -c log_min_error_statement=panic -c log_error_verbosity=terse'
                ' -c log_parameter_max_length_on_error=0','-w','start'])
            owned.capture_process()
        elif state == 'in production':
            owned.start_after = 0
            owned.pg_stopped = False
            owned.capture_process()  # PID/executable/UID/PGDATA/port/start-tick checks.
        else:
            raise RuntimeError('EXISTING_CLUSTER_STATE_REJECTED')
        owned.verify()
        run_bridge(EXISTING_CLUSTER_ID)  # SQL exact identity is checked before every test transaction.
    finally:
        try:
            if started:
                owned.stop()  # Only the process started here; preserve prior stopped/running state.
        finally:
            os.close(owned.fd)
            os.close(owned.parent_fd)


def main(*, existing=False):
    office_guard()
    with office_runtime():
        if existing:
            run_existing()
        else:
            provision.prepare(bridge_acceptance=run_bridge, environment='OFFICE_WSL_AAA_FIXTURE')


if __name__ == '__main__':
    try:
        import argparse
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--existing',action='store_true',help='Use ONLY the pinned existing Office cluster; never initdb')
        args = parser.parse_args()
        main(existing=args.existing)
    except Exception as error:
        # Never print DSN, secrets, SQL parameters or arbitrary exception messages.
        codes = {'OFFICE_WSL_IDENTITY_REJECTED','EXACT_OFFICE_CLUSTER_REQUIRED','EXISTING_CLUSTER_STATE_REJECTED',
                 'ACCEPTANCE_ROOT_ALREADY_EXISTS','DIRTY_WORKTREE_REJECTED','OFFICE_BRANCH_REJECTED'}
        reason = str(error) if type(error) is RuntimeError and str(error) in codes else type(error).__name__
        print('BLOCKED: OFFICE_AAA_POSTGRES_' + reason)
        raise SystemExit(1) from None
