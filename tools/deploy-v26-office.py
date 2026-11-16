#!/usr/bin/env python3
"""Office WSL: authorized, pinned V26 deployment with guarded code rollback."""
import argparse
import base64
import getpass
import hashlib
import os
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = '69279d22c0f31ef3624a2676ce4edd9eb1863bf7'


def source(commit,path):
    return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT,text=True)


def build_artifact():
    migration_hash = hashlib.sha256(source(TARGET,'migrations/versions/011_package_catalog.sql').encode()).hexdigest()
    for path in sorted((ROOT/'.local/v26-release-dry-run').glob('*/manifest.json'),reverse=True):
        if path.is_symlink() or path.parent.is_symlink():continue
        if path.stat().st_uid!=os.getuid() or path.parent.stat().st_mode & 0o077:continue
        manifest=json.loads(path.read_text())
        if manifest.get('commit')!=TARGET or manifest.get('build_acceptance')!='PASS':continue
        for name,key in [('source.tar','source_sha256'),('frontend-dist.tar','frontend_dist_sha256')]:
            if hashlib.sha256((path.parent/name).read_bytes()).hexdigest()!=manifest[key]:
                raise RuntimeError('LOCAL_ARTIFACT_HASH_REJECTED')
        if manifest.get('migration_sha256')!=migration_hash:
            raise RuntimeError('LOCAL_MIGRATION_HASH_REJECTED')
        manifest['artifact_directory']=str(path.parent)
        return manifest
    spec = importlib.util.spec_from_file_location('release_builder',ROOT/'tools/prepare-v26-dry-run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.prepare(TARGET)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-approved',required=True,action='store_true')
    parser.parse_args()
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    # Build the already accepted source, not the new handoff/tool commit.
    manifest = build_artifact()
    archive = Path(manifest['artifact_directory'])/'frontend-dist.tar'
    credentials = dict(username=input('Mevcut V2.6 ADMIN kullanıcı adı: '),
                       password=getpass.getpass('Mevcut V2.6 ADMIN parolası: '))
    values = dict(TARGET=TARGET,DIST_B64=base64.b64encode(archive.read_bytes()).decode(),
                  DIST_SHA=manifest['frontend_dist_sha256'],ADMIN=credentials,
                  MIGRATION_SQL=source(TARGET,'migrations/versions/011_package_catalog.sql'),
                  HELPER_SOURCE=source(TARGET,'tools/v26_backup_migration_remote.py'))
    payload = '\n'.join(key+' = '+repr(value) for key,value in values.items())+'\n'
    payload += source(commit,'tools/deploy_v26_remote.py')+'\nraise SystemExit(main())\n'
    compile(payload,'pinned_v26_deploy','exec')
    command = ['ssh','-i',str(Path.home()/'.ssh/mikrotik_manager_ed25519'),
               '-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
               '-o','ConnectTimeout=10','mikadmin@185.139.5.51','python3 -']
    try:
        # Credentials travel through encrypted stdin only, never argv or a file.
        return subprocess.run(command,input=payload,text=True).returncode
    finally:
        credentials.clear()


if __name__ == '__main__':
    raise SystemExit(main())
