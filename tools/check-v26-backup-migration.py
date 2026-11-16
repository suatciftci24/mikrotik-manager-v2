#!/usr/bin/env python3
"""Office WSL: one SSH call; live catalog reads + isolated restore/migration only."""
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def payload():
    # Read tracked migration from the exact local commit, not an uncommitted file.
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    migration = subprocess.check_output(['git','show',commit+':migrations/versions/011_package_catalog.sql'],cwd=ROOT,text=True)
    worker = subprocess.check_output(['git','show',commit+':tools/v26_backup_migration_remote.py'],cwd=ROOT,text=True)
    compile(worker,'remote_worker','exec')
    return 'SOURCE_COMMIT = '+repr(commit)+'\nMIGRATION_SQL = '+repr(migration)+'\n'+worker+'\nraise SystemExit(main())\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-isolated',action='store_true',required=True)
    parser.parse_args()
    command = ['ssh','-i',str(Path.home()/'.ssh/mikrotik_manager_ed25519'),
               '-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
               '-o','ConnectTimeout=10','mikadmin@185.139.5.51','python3 -']
    return subprocess.run(command,input=payload(),text=True).returncode


if __name__ == '__main__':
    raise SystemExit(main())
