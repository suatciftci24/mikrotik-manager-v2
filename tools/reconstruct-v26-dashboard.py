"""Reconstruct fffac4a in a disposable directory; no sockets/DB/services/stash."""
import argparse
from pathlib import Path
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'fffac4a02e26a9f309197adacbf119c9b2e79602'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-name-pattern')
    args = parser.parse_args()
    # Use only existing packages, never install or import application backend code.
    binary = ROOT / 'frontend/node_modules/@esbuild/linux-x64/bin/esbuild'
    if not binary.is_file():
        raise RuntimeError('LOCAL_ESBUILD_BINARY_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='v26-historical-') as directory:
        target = Path(directory)
        raw = subprocess.run(['git', 'archive', COMMIT, 'frontend/src',
                              'deploy/v1-inventory/v26-browser-acceptance.mjs',
                              'frontend/package.json', 'frontend/package-lock.json'],
                             cwd=ROOT, check=True, capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            for member in archive.getmembers():
                if not (member.isfile() or member.isdir()) or not (target / member.name).resolve().is_relative_to(target):
                    raise RuntimeError('ARCHIVE_ENTRY_REJECTED')
            archive.extractall(target, filter='data')
        for name in ('package.json', 'package-lock.json'):
            if (target / 'frontend' / name).read_bytes() != (ROOT / 'frontend' / name).read_bytes():
                raise RuntimeError('HISTORICAL_DEPENDENCY_LOCK_MISMATCH')
        runner = target / 'deploy/v1-inventory/v26-browser-acceptance.mjs'
        (target / 'manifest.json').write_text(json.dumps(dict(commit=COMMIT,
            runner_sha256=hashlib.sha256(runner.read_bytes()).hexdigest(), synthetic_only=True)))
        entry = target / 'frontend/historical-entry.tsx'
        entry.write_text("export {DashboardV1HealthView} from './src/components/DashboardV1Health';")
        subprocess.run([str(binary), str(entry), '--bundle', '--platform=node', '--format=cjs',
                        '--jsx=automatic', '--packages=external', '--outfile=' + str(target / 'historical.cjs')],
                       cwd=target, check=True, capture_output=True)
        environment = {k: v for k, v in os.environ.items() if not k.startswith(('V2_', 'PG'))}
        environment['V26_HISTORICAL_ROOT'] = str(target)
        node_args = ['node']
        if args.test_name_pattern:
            node_args.append('--test-name-pattern=' + args.test_name_pattern)
        return subprocess.run([*node_args, 'tests/dashboardHistorical.test.mjs'], cwd=ROOT / 'frontend',
                              env=environment, timeout=30).returncode


if __name__ == '__main__':
    raise SystemExit(main())
