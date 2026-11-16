#!/usr/bin/env python3
"""VDS-only test process; never inherit the central panel's DB credentials."""
import os
from pathlib import Path
import re
import subprocess
import sys

APP=Path('/srv/mikrotik-v26-next')


def main():
    if Path.cwd()!=APP or APP.resolve()!=APP:
        raise RuntimeError('VDS_CHECKOUT_REQUIRED')
    modules=sys.argv[1:]
    if not modules or not all(re.fullmatch(r'backend\.tests\.test_[a-z0-9_]+(?:\.[A-Za-z0-9_]+)*',name) for name in modules):
        raise RuntimeError('EXPLICIT_TARGET_TESTS_REQUIRED')
    python=APP/'.local/central/dev-venv/bin/python'
    if not python.is_file():raise RuntimeError('CENTRAL_DEV_ENVIRONMENT_REQUIRED')
    env={key:value for key,value in os.environ.items() if not key.startswith(('V2_','PG'))}
    env.update(PYTHONPATH=str(APP/'backend'),PYTHONDONTWRITEBYTECODE='1',
               V2_DATABASE_URL='postgresql+psycopg://isolated_only@127.0.0.1:1/isolated_only')
    return subprocess.run([str(python),'-B','-m','unittest',*modules],cwd=APP,env=env).returncode


if __name__=='__main__':raise SystemExit(main())
