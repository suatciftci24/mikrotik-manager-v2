#!/usr/bin/env python3
"""Office WSL: stream a read-only V2 diagnosis; no remote staging or updater execution."""
import ast
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path('/home/suatpc/Codex-Projects/mikrotik-manager-v2')
TARGET = '7bb617c4838c1bd94b8cbe612981cabe5186b6b1'


def payload():
    # Reuse only the existing diagnostic helpers, never execute updater top-level.
    source = (ROOT / 'deploy/cebeci-v2-pilot/update-approved-vds.py').read_text()
    tree = ast.parse(source)
    helpers = '\n\n'.join(ast.get_source_segment(source, node) for node in tree.body
                           if isinstance(node, ast.FunctionDef) and node.name in {'need', 'run', 'sql'})
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', TARGET, 'migrations/versions'], cwd=ROOT, text=True).splitlines()
    objects = set()
    for path in paths:
        if not path.endswith('.sql') or path.endswith('.down.sql'):
            continue
        text = subprocess.check_output(['git', 'show', TARGET + ':' + path], cwd=ROOT, text=True)
        for name in re.findall(r'CREATE TABLE (?:IF NOT EXISTS )?([a-z0-9_.]+)\s*\(', text):
            objects.add(name if '.' in name else 'public.' + name)
    if not objects:
        raise ValueError('target objects missing')
    return '''import json, os, re, shutil, subprocess, sys
from pathlib import Path
B = Path('/srv/mikrotik-manager-v2-pilot')
PG = '/usr/lib/postgresql/16/bin/'
STEP = 'migration-diagnosis'
REASON = 'DIAGNOSIS_FAILED'
PGENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'PGCONNECT_TIMEOUT': '5',
 'PGOPTIONS': '-c default_transaction_read_only=on -c statement_timeout=15000'}
''' + helpers + '\nobjects = ' + repr(sorted(objects)) + '''
try:
    need(os.geteuid() == 0 and B.resolve() == B, 'V2_ROOT_INVALID')
    RUNUSER = shutil.which('runuser', path='/usr/sbin:/usr/bin:/sbin:/bin')
    need(RUNUSER is not None, 'RUNUSER_NOT_FOUND')
    identity = sql("SELECT current_database(),current_user,current_setting('port'),current_setting('data_directory'),current_setting('transaction_read_only')").decode().strip()
    need(identity.split('|') == ['mikrotik_manager_v2','v2_pilot_maint','55432',str(B/'postgres'),'on'], 'V2_IDENTITY_MISMATCH')
    print('PASS isolated-V2 identity; read_only=on', flush=True)
    missing = []
    for name in objects:
        present = sql("SELECT to_regclass('" + name + "') IS NOT NULL").decode().strip() == 't'
        print('object=' + name + ' present=' + str(present).lower(), flush=True)
        if not present:
            missing.append(name)
    if 'v2_demo.schema_state' not in missing:
        # Only the integer store version; no markers, users, hashes or row data.
        versions = sql('SELECT version FROM v2_demo.schema_state ORDER BY version LIMIT 20').decode().splitlines()
        need(all(re.fullmatch(r'[0-9]{1,10}', v) for v in versions), 'VERSION_RECORD_INVALID')
        print('store_version_records=' + json.dumps(versions), flush=True)
    else:
        print('store_version_records=UNAVAILABLE', flush=True)
    legacy = [name for name in missing if name.startswith('public.')]
    active = [name for name in missing if not name.startswith('public.')]
    print('legacy_schema_missing=' + json.dumps(legacy), flush=True)
    print('active_workspace_missing=' + json.dumps(active), flush=True)
    print('migration_revision_checksum_ledger=NO_REPOSITORY_CONTRACT', flush=True)
    print('full_schema_compatibility=UNVERIFIED', flush=True)
    print('BLOCKED reason=' + ('ACTIVE_WORKSPACE_MISSING' if active else 'MIGRATION_HISTORY_UNVERIFIABLE'), flush=True)
    sys.exit(2)
except Exception:
    print('BLOCKED reason=' + REASON + '; no secrets printed', flush=True)
    sys.exit(1)
'''


def main():
    try:
        code = payload()
    except Exception:
        print('BLOCKED reason=LOCAL_DIAGNOSTIC_PREPARATION_FAILED')
        return 1
    # One SSH connection, no retry, no file transfer, no service/API commands.
    command = 'sudo python3 -I -c ' + shlex.quote(code)
    return subprocess.run(['ssh', '-tt', '-i', '/home/suatpc/.ssh/mikrotik_manager_ed25519',
                           '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes',
                           '-o', 'ConnectTimeout=10', 'mikadmin@185.139.5.51', command]).returncode


if __name__ == '__main__':
    raise SystemExit(main())
