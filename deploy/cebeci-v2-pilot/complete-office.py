#!/usr/bin/env python3
"""Run on the office machine. Never print subprocess errors or secret values."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, unquote

ROOT = Path('/home/suatpc/Codex-Projects/mikrotik-manager-v2')
PACKAGE = ROOT / 'deploy/cebeci-v2-pilot'
SSH = ['ssh', '-i', '/home/suatpc/.ssh/mikrotik_manager_ed25519', '-o', 'IdentitiesOnly=yes',
       '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10']
HOST = 'mikadmin@185.139.5.51'
STEP = 'preflight'


def run(args, **kwargs):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        raise RuntimeError('command failed')
    return result.stdout


def private(path, directory=False):
    info = path.lstat()
    if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)):
        raise RuntimeError('private path rejected')


def export():
    global STEP
    STEP = 'office-read-only-export'
    assert Path.cwd().resolve() == ROOT and os.getuid() != 0
    # Only this V2 repo's configuration and this repo's running processes are eligible.
    configured = os.environ.get('V2_DATABASE_URL')
    if configured is None and (ROOT / '.env').is_file():
        private(ROOT / '.env')
        for line in (ROOT / '.env').read_text().splitlines():
            if line.startswith('V2_DATABASE_URL='):
                configured = line.split('=', 1)[1].strip().strip('"\'')
    if configured is None:
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if (proc / 'cwd').resolve() not in (ROOT, ROOT / 'backend'):
                    continue
                values = (proc / 'environ').read_bytes().split(b'\0')
                urls = [v.split(b'=', 1)[1].decode() for v in values if v.startswith(b'V2_DATABASE_URL=')]
                if urls:
                    if configured is not None and configured != urls[0]:
                        raise RuntimeError('ambiguous config')
                    configured = urls[0]
            except (PermissionError, FileNotFoundError, ProcessLookupError):
                continue
    # Extract the existing repository default without logging or embedding its password.
    if configured is None:
        import ast
        tree = ast.parse((ROOT / 'backend/app/core/config.py').read_text())
        configured = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                          and isinstance(n.value, str) and n.value.startswith('postgresql+psycopg://'))
    url = urlsplit(configured)
    assert (url.scheme, url.hostname, url.port, url.path, url.username) == (
        'postgresql+psycopg', '127.0.0.1', 55432, '/mikrotik_manager_v2', 'v2_local')
    assert not url.query
    target = ROOT / '.local/admin-transfer'
    if not target.exists():
        target.mkdir(mode=0o700)
    private(target, True)
    bundle = target / 'admin-transfer.jsonl'
    if bundle.exists() or bundle.is_symlink():
        private(bundle)
        data = json.loads(bundle.read_text())
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(data['exported_at'])).total_seconds()
        assert -300 <= age < 86400
        return bundle
    password = unquote(url.password or '')
    assert password and not any(c in password for c in '\r\n\0')
    existing_passfile = os.environ.get('PGPASSFILE')
    if existing_passfile is None and (Path.home() / '.pgpass').exists():
        existing_passfile = str(Path.home() / '.pgpass')
    temporary_passfile = existing_passfile is None
    if temporary_passfile:
        fd, pgfile = tempfile.mkstemp(prefix='pgpass-', dir=target)
    else:
        pgfile = str(Path(existing_passfile).absolute())
        private(Path(pgfile))
    created_bundle = False
    try:
        if temporary_passfile:
            with os.fdopen(fd, 'w') as stream:
                escaped = password.replace('\\', '\\\\').replace(':', '\\:')
                stream.write('127.0.0.1:55432:mikrotik_manager_v2:v2_local:' + escaped + '\n')
        with bundle.open('x'):
            pass
        created_bundle = True
        os.chmod(bundle, 0o600)
        private(bundle)
        env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
        env.update(PGPASSFILE=pgfile, PGCONNECT_TIMEOUT='5')
        run(['/usr/lib/postgresql/16/bin/psql', '-X', '-q', '-w', '-h', '127.0.0.1', '-p', '55432',
             '-U', 'v2_local', '-d', 'mikrotik_manager_v2', '-f', str(PACKAGE / 'export-admin.psql')], env=env)
        private(bundle)
        assert bundle.stat().st_size > 0
    except BaseException:
        # Only remove our own failed export artifact, never an existing handoff.
        if created_bundle:
            bundle.unlink()
        raise
    finally:
        if temporary_passfile:
            Path(pgfile).unlink()
    return bundle


def main():
    global STEP
    if sys.flags.optimize:
        raise RuntimeError('optimized execution forbidden')
    os.umask(0o077)
    os.chdir(ROOT)
    if sys.argv[1:] != ['--export-only']:
        assert not run(['git', 'status', '--porcelain'], cwd=ROOT).strip()
    bundle = export()
    print('PASS: office ADMIN read-only export (private file)', flush=True)
    if sys.argv[1:] == ['--export-only']:
        return
    assert not sys.argv[1:]
    STEP = 'ssh-private-staging'
    stage = run(SSH + ['-o', 'BatchMode=yes', HOST,
                      'umask 077; mktemp -d /home/mikadmin/v2-complete.XXXXXXXX']).decode().strip()
    import re
    assert re.fullmatch(r'/home/mikadmin/v2-complete\.[A-Za-z0-9]{8}', stage)
    STEP = 'source-archive'
    with tempfile.TemporaryDirectory(prefix='source-', dir=bundle.parent) as temp:
        archive = Path(temp) / 'app.tar'
        # Tracked source only; no .env, .local, venv or handoff in the application archive.
        run(['git', 'archive', '--format=tar', '--output=' + str(archive), 'HEAD'], cwd=ROOT)
        STEP = 'sftp-private-transfer'
        batch = '\n'.join(f'put {src} {stage}/{name}' for src, name in (
            (archive, 'app.tar'), (bundle, 'admin-transfer.jsonl'),
            (PACKAGE / 'complete-vds.py', 'complete-vds.py'))) + '\n'
        batch += ''.join(f'chmod 600 {stage}/{name}\n' for name in ('app.tar', 'admin-transfer.jsonl', 'complete-vds.py'))
        run(['sftp', '-b', '-', '-i', '/home/suatpc/.ssh/mikrotik_manager_ed25519',
             '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', HOST], input=batch.encode())
    STEP = 'vds-completion'
    # sudo may ask for the VDS operator's password on the real terminal, never in argv/logs.
    result = subprocess.run(SSH + ['-t', HOST, f'sudo python3 {stage}/complete-vds.py {stage}'])
    if result.returncode:
        raise RuntimeError('VDS completion failed')
    print('PASS: transfer and isolated V2 completion; actual ADMIN password login remains untested')


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt):
        print(f'BLOCKED: {STEP}; no secret diagnostics printed; no automatic retry', file=sys.stderr)
        sys.exit(1)
