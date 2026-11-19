#!/usr/bin/env python3
"""Create a pinned source handoff and review manifest. Never deploy or contact VDS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def prepare():
    commit = git('rev-parse', 'HEAD')
    baseline = git('rev-parse', 'b4e78a4^{commit}')
    subprocess.run(['git', 'merge-base', '--is-ancestor', baseline, commit], cwd=ROOT, check=True)
    paths = ['release.json', 'backend/app', 'migrations', 'frontend']
    names = git('ls-tree', '-r', '--name-only', commit, '--', *paths).splitlines()
    for name in names:
        if re.search(r'(^|/)(\.env($|\.)|\.local/|node_modules/)|\.(dump|key|p12|pfx)$', name):
            raise RuntimeError('Private or generated source path rejected')
    output = ROOT/'.local/v26-release-dry-run'
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = Path(tempfile.mkdtemp(prefix=commit[:12]+'-', dir=output))
    archive = destination/'source.tar'
    with archive.open('xb') as stream:
        subprocess.run(['git', 'archive', '--format=tar', commit, '--', *paths],
                       cwd=ROOT, stdout=stream, check=True)
    archive.chmod(0o600)
    migration = subprocess.check_output(['git', 'show', commit+':migrations/versions/011_package_catalog.sql'], cwd=ROOT)
    manifest = dict(mode='DRY_RUN_ONLY', deploy_enabled=False, cleanup_enabled=False,
                    commit=commit, vds_baseline=baseline, target='/srv/mikrotik-v26-next',
                    source_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                    migration_sha256=hashlib.sha256(migration).hexdigest(),
                    source_only=True, build_acceptance='NOT_INCLUDED',
                    live_schema_acceptance='NOT_VERIFIED',
                    baseline_provenance='USER_REPORTED_VDS_HEAD',
                    reported_counts=dict(tables=17, users=2, workspace_subscribers=2,
                                         workspace_operations=12, router_records=1),
                    prerequisites=['fresh_target_and_catalog_inventory', 'verified_private_backup_and_restore',
                                   'isolated_migration_rehearsal', 'built_frontend_artifact',
                                   'explicit_live_approval'],
                    rollback='restore prior code; retain additive catalog; DB restore requires separate approval')
    build_root = destination/'build'
    build_root.mkdir(mode=0o700)
    with tarfile.open(archive) as source:
        source.extractall(build_root, filter='data')
    dependencies = ROOT/'frontend/node_modules'
    if not dependencies.is_dir():
        raise RuntimeError('Local build dependencies absent; no install attempted')
    (build_root/'frontend/node_modules').symlink_to(dependencies, target_is_directory=True)
    with (destination/'frontend-build.log').open('x') as log:
        subprocess.run(['npm', 'run', 'build'], cwd=build_root/'frontend',
                       env={**os.environ, 'V2_BUILD_COMMIT': commit},
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    built = destination/'frontend-dist.tar'
    with tarfile.open(built, 'x') as package:
        package.add(build_root/'frontend/dist', arcname='dist')
    built.chmod(0o600)
    manifest['build_acceptance'] = 'PASS'
    manifest['frontend_dist_sha256'] = hashlib.sha256(built.read_bytes()).hexdigest()
    manifest['prerequisites'].remove('built_frontend_artifact')
    path = destination/'manifest.json' 
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    path.chmod(0o600)
    print(path)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', required=True, action='store_true')
    parser.parse_args()
    prepare()
