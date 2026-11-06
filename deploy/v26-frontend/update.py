"""Offline selective V26 frontend update. No SSH, service, backend or DB operations.
CLI writes to the VDS only for explicitly approved apply/rollback invocations.
"""
import argparse
import ctypes
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.request import build_opener, HTTPRedirectHandler
from urllib.parse import urlparse

CHANGED = 'src/components/QuickActions.tsx'
CONFIGS = ('package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts', 'index.html')
TARGET = Path('/srv/mikrotik-manager-v26/frontend')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular(path):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_file():
        raise ValueError('REGULAR_FILE_REQUIRED: '+str(path))
    return path.read_bytes()


def tree(root):
    root = Path(root).absolute()
    if root.resolve() != root or not root.is_dir():
        raise ValueError('REAL_DIRECTORY_REQUIRED: '+str(root))
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('SYMLINK_REJECTED')
        if p.is_file():
            result[p.relative_to(root).as_posix()] = digest(regular(p))
        elif not p.is_dir():
            raise ValueError('SPECIAL_FILE_REJECTED')
    return result


def inputs(root):
    return {**{'src/'+k:v for k,v in tree(root/'src').items()},
            **{'public/'+k:v for k,v in tree(root/'public').items()},
            **{k:digest(regular(root/k)) for k in CONFIGS}}


def write_json(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')


def manifest(bundle):
    m = json.loads(regular(bundle/'manifest.json'))
    if m['changed'] != [CHANGED] or set(m['before']) != set(m['after']):
        raise ValueError('SELECTIVE_MANIFEST_REQUIRED')
    if {k for k in m['before'] if m['before'][k] != m['after'][k]} != {CHANGED}:
        raise ValueError('UNEXPECTED_SOURCE_CHANGE')
    if tree(bundle/'payload') != {CHANGED:m['after'][CHANGED]} or tree(bundle/'dist') != m['dist']:
        raise ValueError('BUNDLE_INTEGRITY_FAILED')
    validate_dist(bundle/'dist')
    return m


def validate_dist(root):
    html = regular(root/'index.html').decode()
    assets = re.findall(r'(?:src|href)="(/?assets/[^"?#]+)', html)
    if not assets:
        raise ValueError('DIST_ASSETS_REQUIRED')
    for name in assets:
        p = root/name.lstrip('/')
        if not p.resolve().is_relative_to(root.resolve()):
            raise ValueError('ASSET_PATH_REJECTED')
        regular(p)
    return assets


def pack(baseline, candidate, bundle):
    before, after = inputs(baseline), inputs(candidate)
    if before.keys() != after.keys() or {k for k in before if before[k] != after[k]} != {CHANGED}:
        raise ValueError('ONLY_QUICK_ACTIONS_CHANGE_ALLOWED')
    validate_dist(candidate/'dist')
    validate_dist(baseline/'dist')
    baseline_dist = tree(baseline/'dist')
    for name, value in baseline_dist.items():
        if name.startswith('assets/') and (candidate/'dist'/name).exists() and digest(regular(candidate/'dist'/name)) != value:
            raise ValueError('OLD_ASSET_NAME_COLLISION')
    bundle.mkdir(mode=0o700)  # never replace a previous package
    (bundle/'payload/src/components').mkdir(parents=True)
    shutil.copy2(candidate/CHANGED, bundle/'payload'/CHANGED)
    shutil.copytree(candidate/'dist', bundle/'dist')
    # Keep old hashed chunks for already open browsers and lazy imports.
    for name in baseline_dist:
        if name.startswith('assets/') and not (bundle/'dist'/name).exists():
            (bundle/'dist'/name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(baseline/'dist'/name,bundle/'dist'/name)
    write_json(bundle/'manifest.json', dict(changed=[CHANGED],before=before,after=after,dist_before=baseline_dist,dist=tree(bundle/'dist')))
    manifest(bundle)


def check(target, bundle):
    m = manifest(bundle)
    if inputs(target) != m['before']:
        raise ValueError('TARGET_SOURCE_OR_CONFIG_DRIFT_STOP')
    validate_dist(target/'dist')
    if tree(target/'dist') != m['dist_before']:
        raise ValueError('TARGET_BUILD_DRIFT_STOP')
    return m


@contextmanager
def locked(target):
    # Directory flock; do not create a lockfile on the server.
    fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('HTTP_REDIRECT_REJECTED')


def verify(target, bundle, url=None):
    m = manifest(bundle)
    if inputs(target) != m['after'] or tree(target/'dist') != m['dist']:
        raise ValueError('POST_UPDATE_INTEGRITY_FAILED')
    assets = validate_dist(target/'dist')
    if url:
        parsed = urlparse(url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('LOOPBACK_GET_ONLY_URL_REQUIRED')
        for name in ['index.html', *[p.lstrip('/') for p in assets]]:
            with build_opener(NoRedirect).open(url.rstrip('/')+'/'+name, timeout=10) as response:
                if response.geturl() != url.rstrip('/')+'/'+name or response.read() != regular(target/'dist'/name):
                    raise ValueError('SERVED_ASSET_MISMATCH')


def exchange(left, right):
    # Linux atomic directory exchange; fail closed if unsupported.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(left), -100, os.fsencode(right), 2):
        raise OSError(ctypes.get_errno(), 'ATOMIC_EXCHANGE_FAILED')


def apply(target, bundle, backup):
    with locked(target):
        m = check(target,bundle)
        old_dist = tree(target/'dist')
        backup.mkdir(mode=0o700)
        shutil.copy2(target/CHANGED, backup/'QuickActions.tsx')
        shutil.copytree(target/'dist', backup/'dist')
        write_json(backup/'receipt.json', dict(before=m['before'],after=m['after'],dist_before=old_dist,dist_after=m['dist']))
        if tree(backup/'dist') != old_dist or digest(regular(backup/'QuickActions.tsx')) != m['before'][CHANGED]:
            raise ValueError('BACKUP_INTEGRITY_FAILED')
        # Stage on target filesystem. Copy failures occur before the live tree changes.
        with tempfile.TemporaryDirectory(prefix='.v26-stage-',dir=target) as temp:
            stage = Path(temp)
            shutil.copytree(bundle/'dist',stage/'dist')
            shutil.copy2(bundle/'payload'/CHANGED,stage/'QuickActions.tsx')
            check(target,bundle)
            moved = False
            try:
                exchange(target/'dist',stage/'dist');moved=True
                (stage/'QuickActions.tsx').replace(target/CHANGED)
                verify(target,bundle)
            except Exception:
                if moved:
                    exchange(target/'dist',stage/'dist')
                    shutil.copy2(backup/'QuickActions.tsx',target/CHANGED)
                raise


def rollback(target, backup):
    with locked(target):
        r = json.loads(regular(backup/'receipt.json'))
        if inputs(target) not in (r['before'],r['after']) or tree(target/'dist') not in (r['dist_before'],r['dist_after']):
            raise ValueError('ROLLBACK_TARGET_DRIFT_STOP')
        if tree(backup/'dist') != r['dist_before'] or digest(regular(backup/'QuickActions.tsx')) != r['before'][CHANGED]:
            raise ValueError('ROLLBACK_BACKUP_CORRUPT')
        with tempfile.TemporaryDirectory(prefix='.v26-rollback-',dir=target) as temp:
            stage = Path(temp)
            shutil.copytree(backup/'dist',stage/'dist')
            shutil.copy2(backup/'QuickActions.tsx',stage/'QuickActions.tsx')
            shutil.copy2(target/CHANGED,stage/'current-source.tsx')
            exchange(target/'dist',stage/'dist')
            try:
                (stage/'QuickActions.tsx').replace(target/CHANGED)
                if inputs(target) != r['before'] or tree(target/'dist') != r['dist_before']:
                    raise ValueError('ROLLBACK_VERIFY_FAILED')
            except Exception:
                exchange(target/'dist',stage/'dist')
                (stage/'current-source.tsx').replace(target/CHANGED)
                raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['pack','check','apply','verify','rollback'])
    for name in ('baseline','candidate','bundle','backup'):
        p.add_argument('--'+name,type=Path)
    p.add_argument('--target',type=Path,default=TARGET)
    p.add_argument('--url')
    p.add_argument('--approved-v26-frontend-write',action='store_true')
    args=p.parse_args()
    if args.action=='pack':
        if not all((args.baseline,args.candidate,args.bundle)):p.error('baseline/candidate/bundle required')
        if any(v.resolve().is_relative_to(Path('/srv')) for v in (args.baseline,args.candidate,args.bundle)):
            p.error('pack is LOCAL only')
        pack(args.baseline,args.candidate,args.bundle)
    else:
        if args.target.absolute()!=TARGET or args.target.resolve()!=TARGET:
            p.error('only exact V2.6 frontend target allowed')
        if args.action in ('apply','rollback') and not args.approved_v26_frontend_write:
            p.error('separate explicit deployment approval required')
        if args.action in ('apply','rollback'):
            if not args.backup or args.backup.absolute().parent!=TARGET.parent or not args.backup.name.startswith('frontend-backup-'):
                p.error('new sibling frontend-backup-* required')
        if args.action!='rollback' and not args.bundle:p.error('bundle required')
        if args.action=='check':check(args.target,args.bundle)
        elif args.action=='apply':apply(args.target,args.bundle,args.backup)
        elif args.action=='rollback':rollback(args.target,args.backup)
        else:verify(args.target,args.bundle,args.url)
    print('PASS:',args.action)


if __name__=='__main__':
    try:main()
    except Exception as error:raise SystemExit('BLOCKED: '+str(error))
