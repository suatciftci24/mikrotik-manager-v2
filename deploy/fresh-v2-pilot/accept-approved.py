#!/usr/bin/env python3
"""Root-owned acceptance seal after fresh DB verification and verified new backup.
No daemon-reload/start/restart/enable, and no write to an old installation.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import manage


def main():
    manage.need(sys.argv[1:] == ['--accept-approved'] and os.geteuid() == 0, 'APPROVED_ROOT_ACCEPTANCE_REQUIRED')
    manifest, _, _ = manage.check_sources()
    manage.need(manage.REPO == manage.ROOT/'app', 'INSTALLED_SOURCE_REQUIRED')
    for action in ('verify','backup'):
        argv=['/usr/sbin/runuser','-u','mikrotik-v2-fresh-db','--',str(manage.ROOT/'venv/bin/python'),str(manage.HERE/'manage.py'),action]
        manage.need(subprocess.run(argv,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0, 'VERIFICATION_OR_BACKUP_FAILED')
    path = manage.ROOT/'accepted.json'
    with path.open('x') as output:
        output.write(json.dumps({'profile':'fresh-v2-pilot','manifest_sha256':manage.digest(manifest)})+'\n')
    path.chmod(0o644)
    print('PASS: FRESH_ACCEPTANCE_SEALED; NO_SERVICE_STARTED; RESTORE_DRILL_NOT_PERFORMED')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('BLOCKED: FRESH_ACCEPTANCE_FAILED',file=sys.stderr)
        sys.exit(2)
