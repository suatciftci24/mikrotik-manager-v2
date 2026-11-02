#!/usr/bin/env python3
"""Local-only release handoff. Reuses existing frontend/dist; never SSH/DB/service IO."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile
import manage

AREAS = ('backend/app', 'backend/requirements.txt', 'migrations', 'deploy/fresh-v2-pilot')
REQUIRED = ('backend/app/core/fresh_pilot.py', 'backend/app/services/first_admin.py',
            'deploy/fresh-v2-pilot/manifest.json')


def git(*args):
    return subprocess.check_output(['git', '-C', str(manage.REPO), *args], stderr=subprocess.DEVNULL)


def allowed(name):
    path = PurePosixPath(name)
    return (not path.is_absolute() and '..' not in path.parts
            and not any(part in ('.local', '.git', '.venv', 'node_modules', '__pycache__')
                        or part.startswith('.env') for part in path.parts)
            and path.suffix not in ('.pyc', '.key', '.pem'))


def add_bytes(archive, name, data, mode=0o644):
    item = tarfile.TarInfo(name)
    item.size = len(data)
    item.mode = mode
    item.mtime = 0
    archive.addfile(item, io.BytesIO(data))


def create(output):
    manifest, _, _ = manage.check_sources()
    revision = git('rev-parse', 'HEAD').decode().strip()
    # Include only reviewed, committed source; never silently omit new pilot code.
    for name in REQUIRED:
        git('cat-file', '-e', f'{revision}:{name}')
    manage.need(not git('status', '--porcelain', '--untracked-files=all', '--', *AREAS).strip(),
                'RELEASE_SOURCE_NOT_COMMITTED')
    source = git('archive', '--format=tar', revision, '--', *AREAS)
    build = manage.REPO/'frontend/dist'
    manage.need(build.is_dir() and not build.is_symlink() and build.resolve() == build,
                'EXISTING_FRONTEND_BUILD_REQUIRED')
    manage.need((build/'index.html').is_file(), 'EXISTING_FRONTEND_BUILD_REQUIRED')
    assets = []
    for path in sorted(build.rglob('*')):
        mode = path.lstat().st_mode
        manage.need(not stat.S_ISLNK(mode) and (stat.S_ISREG(mode) or stat.S_ISDIR(mode)),
                    'BUILD_SPECIAL_FILE_REJECTED')
        if path.is_file():
            name = path.relative_to(manage.REPO).as_posix()
            manage.need(allowed(name), 'BUILD_PRIVATE_PATH_REJECTED')
            assets.append((name, path.read_bytes()))
    # Construct fully in memory before exclusive output; partial artifacts are never reused.
    buffer = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(source), mode='r:') as original, \
         tarfile.open(fileobj=buffer, mode='w:') as release:
        for item in original:
            if item.isdir():
                continue
            manage.need(item.isfile() and allowed(item.name), 'SOURCE_MEMBER_REJECTED')
            add_bytes(release, item.name, original.extractfile(item).read(), item.mode & 0o755)
        for name, data in assets:
            add_bytes(release, name, data)
    archive = buffer.getvalue()
    receipt = dict(format=1, git_commit=revision, archive_sha256=hashlib.sha256(archive).hexdigest(),
                   manifest_sha256=hashlib.sha256(manifest).hexdigest(),
                   frontend_build='EXISTING_OUTPUT_NOT_REBUILT_SOURCE_EQUIVALENCE_NOT_ATTESTED',
                   frontend_sha256={name:hashlib.sha256(data).hexdigest() for name,data in assets})
    # Output must be new; existing evidence and archives are preserved.
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (output/'fresh-v2-pilot.tar').open('xb') as target:
        target.write(archive)
    with (output/'receipt.json').open('x') as target:
        target.write(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
    (output/'fresh-v2-pilot.tar').chmod(0o600)
    (output/'receipt.json').chmod(0o600)
    print('PASS: LOCAL_RELEASE_READY; NO_TRANSFER_NO_INSTALL; COMMIT='+revision)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        create(args.output)
    except Exception:
        print('BLOCKED: RELEASE_PRECONDITION_FAILED; KEEP_EXISTING_ARTIFACTS')
        raise SystemExit(2)
