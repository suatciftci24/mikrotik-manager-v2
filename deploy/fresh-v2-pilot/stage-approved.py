#!/usr/bin/env python3
"""Future approved host staging only. Default is offline validation. Never starts services."""
import fnmatch
import grp
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import sys
import manage

ROOT = manage.ROOT
USERS = ('mikrotik-v2-fresh', 'mikrotik-v2-fresh-db')
UNITS = ('mikrotik-v2-fresh-pilot.service', 'mikrotik-v2-fresh-pilot-db.service')
SOURCE_AREAS = ('backend','frontend','migrations','deploy/fresh-v2-pilot')
IGNORED = ('.env*','.local','.git','.venv','node_modules','__pycache__','*.pyc','.pytest_cache')


def source_preflight():
    # Inspect every copy source before reserving the target or creating accounts.
    for name in SOURCE_AREAS:
        source = manage.REPO/name
        manage.need(source.is_dir() and source.resolve() == source, 'SOURCE_DIRECTORY_REJECTED')
        for current, dirs, files in os.walk(source, followlinks=False):
            dirs[:] = [entry for entry in dirs if not any(fnmatch.fnmatch(entry, pattern) for pattern in IGNORED)]
            for entry in dirs + files:
                if not any(fnmatch.fnmatch(entry, pattern) for pattern in IGNORED):
                    path = Path(current)/entry
                    manage.need(not path.is_symlink() and (path.is_dir() or path.is_file()), 'SOURCE_SPECIAL_FILE_REJECTED')
    manage.need((manage.REPO/'frontend/dist/index.html').is_file(), 'PREBUILT_FRONTEND_REQUIRED')


def run(argv):
    manage.need(subprocess.run(argv, env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0, 'STAGING_COMMAND_FAILED')


def preflight():
    manage.check_sources()
    manage.need(os.geteuid() == 0, 'ROOT_REQUIRED_FOR_APPROVED_STAGING')
    for parent in (Path('/srv'), Path('/etc/systemd/system')):
        manage.need(parent.is_dir() and parent.resolve() == parent and not parent.stat().st_mode & 0o022, 'UNSAFE_PARENT')
    # Even an empty preexisting directory is rejected. No adoption or reset path.
    manage.need(not os.path.lexists(ROOT), 'TARGET_ROOT_EXISTS')
    source_preflight()
    for binary in ('/usr/sbin/useradd','/usr/sbin/runuser','/usr/bin/python3',
                   '/usr/lib/postgresql/16/bin/initdb','/usr/lib/postgresql/16/bin/postgres',
                   '/usr/lib/postgresql/16/bin/pg_dump','/usr/lib/postgresql/16/bin/pg_restore'):
        manage.need(Path(binary).is_file() and os.access(binary, os.X_OK), 'HOST_TOOL_REQUIRED')
    run(['/usr/bin/python3','-c','import venv, ensurepip'])
    for user in USERS:
        try:
            pwd.getpwnam(user)
        except KeyError:
            pass
        else:
            raise manage.Blocked('OS_IDENTITY_EXISTS')
        try:
            grp.getgrnam(user)
        except KeyError:
            pass
        else:
            raise manage.Blocked('OS_GROUP_EXISTS')
    for unit in UNITS:
        for base in ('/etc/systemd/system','/run/systemd/system','/usr/lib/systemd/system','/lib/systemd/system'):
            manage.need(not os.path.lexists(Path(base)/unit), 'SERVICE_EXISTS')
    # Retain reservations until staging has completed; never probe SSH or other ports.
    sockets = []
    try:
        for port in (55442,18090):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(sock)
            sock.bind(('127.0.0.1',port))
        return sockets
    except Exception:
        for sock in sockets:
            sock.close()
        raise


def stage():
    reservations = preflight()
    try:
        # Atomic exclusive reservation before any identity/disk mutation.
        ROOT.mkdir(mode=0o755)
        for user in USERS:
            run(['/usr/sbin/useradd','--system','--user-group','--no-create-home','--home-dir',str(ROOT),
                 '--shell','/usr/sbin/nologin',user])
        app = pwd.getpwnam(USERS[0]); db = pwd.getpwnam(USERS[1])
        for name in ('postgres','socket','backups'):
            path = ROOT/name; path.mkdir(mode=0o700); os.chown(path,db.pw_uid,db.pw_gid)
        config = ROOT/'config';config.mkdir(mode=0o750);os.chown(config,db.pw_uid,app.pw_gid);config.chmod(0o2750)
        # Copy ONLY source areas. No .local/.env/venv/credentials/old DB or identity handoff.
        for name in SOURCE_AREAS:
            source = manage.REPO/name
            shutil.copytree(source, ROOT/'app'/name, ignore=shutil.ignore_patterns(*IGNORED))
        local = ROOT/'app/.local';local.mkdir(mode=0o700);os.chown(local,app.pw_uid,app.pw_gid)
        for name in ('postgresql.conf','pg_hba.conf','pg_ident.conf'):
            shutil.copyfile(manage.HERE/name, config/name)
            (config/name).chmod(0o644)
        run(['/usr/sbin/runuser','-u',USERS[1],'--','/usr/lib/postgresql/16/bin/initdb',
             '-D',str(ROOT/'postgres'),'-U',manage.OWNER,'--auth-local=peer','--auth-host=reject','--encoding=UTF8','--locale=C.UTF-8','--no-instructions'])
        run(['/usr/bin/python3','-m','venv',str(ROOT/'venv')])
        run([str(ROOT/'venv/bin/pip'),'install','-r',str(ROOT/'app/backend/requirements.txt')])
        # Exclusive writes; never replace a unit. No daemon-reload/start/restart/enable here.
        for unit in UNITS:
            with (Path('/etc/systemd/system')/unit).open('x') as output:
                output.write((manage.HERE/unit).read_text())
        print('PASS: STAGED_ONLY; DATABASE_NOT_CREATED; SERVICES_NOT_STARTED')
    finally:
        for sock in reservations:
            sock.close()


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--stage-approved']:
            stage()
        elif not sys.argv[1:]:
            manage.check_sources()
            print('PASS: OFFLINE_ONLY; STAGING_NOT_AUTHORIZED_OR_EXECUTED')
        else:
            raise manage.Blocked('ARGUMENT_REJECTED')
    except Exception:
        print('BLOCKED: FRESH_STAGING_FAILED; KEEP_ARTIFACTS_NO_RESET_NO_RESUME', file=sys.stderr)
        sys.exit(2)
