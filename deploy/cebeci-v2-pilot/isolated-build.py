#!/usr/bin/env python3
"""Repeatable V2-only dependency/build repair. No SQL, identities, services or OS packages."""
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request

BASE = Path('/srv/mikrotik-manager-v2-pilot')


class BuildBlocked(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def classify(result, phase):
    error = (result.stdout + result.stderr).lower()
    for fragments, suffix in (
        ((b'double-loading config', b'double-loading "user" configs', b'double-loading "global" configs'), 'CONFIG_SOURCE_COLLISION'),
        ((b'npm ci can only install packages', b'package.json and package-lock.json are in sync', b'package.json and package-lock.json or npm-shrinkwrap.json are in sync'), 'LOCKFILE_OUT_OF_SYNC'),
        ((b'npm does not support node.js',), 'RUNTIME_INCOMPATIBLE'),
        ((b'eai_again', b'enotfound', b'temporary failure in name resolution', b'name or service not known'), 'NETWORK_DNS'),
        ((b'certificate_verify_failed', b'certificate verify failed', b'unable_to_verify', b'self signed certificate', b'unable_to_get_issuer_cert', b'cert_has_expired'), 'NETWORK_TLS'),
        ((b'etimedout', b'read timed out', b'connecttimeout', b'connection timed out'), 'NETWORK_TIMEOUT'),
        ((b'econnrefused', b'connection refused', b'network is unreachable'), 'NETWORK_UNREACHABLE'),
        ((b'permission denied', b'eacces', b'eperm'), 'PERMISSION_DENIED'),
        ((b'no space left on device', b'enospc'), 'DISK_FULL'),
        ((b'ensurepip is not available', b'no module named ensurepip'), 'ENSUREPIP_MISSING'),
        ((b'no module named venv',), 'VENV_MODULE_MISSING'),
        ((b'no module named pip',), 'PIP_MISSING'),
        ((b'no matching distribution found', b'could not find a version that satisfies'), 'PACKAGE_UNAVAILABLE'),
        ((b'ebadengine', b'unsupported engine', b'requires a different python'), 'RUNTIME_INCOMPATIBLE'),
        ((b'heap out of memory',), 'HEAP_EXHAUSTED'),
        ((b'cannot find module @rollup', b'cannot find module \'@rollup', b'cannot find module \'@esbuild', b'you installed esbuild for another platform'), 'PLATFORM_PACKAGE_MISSING'),
        ((b'error ts',), 'TYPESCRIPT_FAILED'),
        ((b'error during build',), 'VITE_FAILED'),
        ((b'glibc_', b'error while loading shared libraries'), 'SYSTEM_LIBRARY_MISSING')):
        if any(fragment in error for fragment in fragments):
            return 'V2_BUILD_' + phase + '_' + suffix
    if phase == 'NPM_VERSION':
        if b'cannot find module' in error or b'module_not_found' in error:
            return 'V2_BUILD_NPM_VERSION_CLI_MODULE_MISSING'
        if b'no such file or directory' in error and b'node' in error:
            return 'V2_BUILD_NPM_VERSION_PATH_NODE_MISSING'
        if b'syntaxerror:' in error:
            return 'V2_BUILD_NPM_VERSION_RUNTIME_SYNTAX_ERROR'
    return 'V2_BUILD_' + phase + ('_PROCESS_KILLED' if result.returncode < 0 else '_FAILED')


def command(args, phase, env, cwd=None, check=True):
    try:
        result = subprocess.run(args, capture_output=True, env=env, cwd=cwd, timeout=600)
    except FileNotFoundError:
        raise BuildBlocked('V2_BUILD_' + phase + '_EXECUTABLE_MISSING') from None
    except PermissionError:
        raise BuildBlocked('V2_BUILD_' + phase + '_PERMISSION_DENIED') from None
    except subprocess.TimeoutExpired:
        raise BuildBlocked('V2_BUILD_' + phase + '_TIMEOUT') from None
    if check and result.returncode:
        raise BuildBlocked(classify(result, phase))
    return result


def owned(path, directory=False, label='PATH'):
    try:
        s = path.lstat()
    except FileNotFoundError:
        raise BuildBlocked('V2_BUILD_' + label + '_MISSING') from None
    if path.resolve() != path or stat.S_ISLNK(s.st_mode):
        raise BuildBlocked('V2_BUILD_' + label + '_SYMLINK_REJECTED')
    if not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)):
        raise BuildBlocked('V2_BUILD_' + label + '_TYPE_REJECTED')
    if s.st_uid != 0:
        raise BuildBlocked('V2_BUILD_' + label + '_OWNER_MISMATCH')
    if s.st_mode & 0o022:
        raise BuildBlocked('V2_BUILD_' + label + '_WRITABLE_BY_OTHERS')
    if not directory and s.st_nlink != 1:
        raise BuildBlocked('V2_BUILD_' + label + '_HARDLINK_REJECTED')


def private_dir(path):
    if not path.exists():
        path.mkdir(mode=0o700)
    owned(path, True)


def environment(base):
    env = {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
           'HOME': str(base / 'build-home'), 'LC_ALL': 'C', 'PIP_CONFIG_FILE': '/dev/null',
           'npm_config_userconfig': str(base / 'build-home/npm-user.npmrc'),
           'npm_config_cache': str(base / 'build-home/npm-cache'),
           'npm_config_globalconfig': str(base / 'build-home/npm-global.npmrc'), 'npm_config_global': 'false',
           'npm_config_registry': 'https://registry.npmjs.org', 'npm_config_update_notifier': 'false'}
    env['npm_config_ignore_scripts'] = 'true'  # Explicit build runs; prebuild/postbuild hooks do not.
    for key in ('HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY', 'https_proxy', 'http_proxy', 'no_proxy'):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def prepare_npm_configs(base):
    """Separate config sources: npm rejects loading one file at two config levels."""
    for name in ('npm-user.npmrc', 'npm-global.npmrc'):
        path = base / 'build-home' / name
        if not path.exists() and not path.is_symlink():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        owned(path, label='NPM_CONFIG')
        if path.stat().st_mode & 0o777 != 0o600:
            raise BuildBlocked('V2_BUILD_NPM_CONFIG_MODE_REJECTED')
        if path.read_bytes():
            raise BuildBlocked('V2_BUILD_NPM_CONFIG_NONEMPTY_STOP')


def download(url, phase, maximum=100 * 1024 * 1024):
    hosts = ('nodejs.org', 'pypi.org', 'files.pythonhosted.org')
    if urllib.parse.urlsplit(url).scheme != 'https' or urllib.parse.urlsplit(url).hostname not in hosts:
        raise BuildBlocked('V2_BUILD_DOWNLOAD_ORIGIN_REJECTED')
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != 'https' or final.hostname not in hosts:
                raise BuildBlocked('V2_BUILD_DOWNLOAD_REDIRECT_REJECTED')
            value = response.read(maximum + 1)
            if len(value) > maximum:
                raise BuildBlocked('V2_BUILD_DOWNLOAD_SIZE_REJECTED')
            return value
    except urllib.error.HTTPError:
        raise BuildBlocked('V2_BUILD_' + phase + '_HTTP_FAILED') from None
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, 'reason', error)
        if isinstance(reason, socket.gaierror):
            suffix = 'NETWORK_DNS'
        elif isinstance(reason, ssl.SSLError):
            suffix = 'NETWORK_TLS'
        elif isinstance(reason, TimeoutError):
            suffix = 'NETWORK_TIMEOUT'
        elif getattr(reason, 'errno', None) == errno.EPERM:
            suffix = 'SOCKET_EPERM'
        else:
            suffix = 'NETWORK_UNREACHABLE'
        raise BuildBlocked('V2_BUILD_' + phase + '_' + suffix) from None


def pip_bootstrap(venv, tools, env):
    python = str(venv / 'bin/python')
    if command([python, '-I', '-m', 'pip', '--version'], 'PY_PIP_CHECK', env, check=False).returncode == 0:
        return
    info = json.loads(download('https://pypi.org/pypi/pip/json', 'PY_BOOTSTRAP', 5 * 1024 * 1024))
    wheel = next((item for item in info['urls'] if re.fullmatch(r'pip-[0-9.]+-py3-none-any.whl', item['filename'])), None)
    if wheel is None:
        raise BuildBlocked('V2_BUILD_PIP_WHEEL_UNAVAILABLE')
    payload = download(wheel['url'], 'PY_BOOTSTRAP', 10 * 1024 * 1024)
    if hashlib.sha256(payload).hexdigest() != wheel['digests']['sha256']:
        raise BuildBlocked('V2_BUILD_PIP_CHECKSUM_REJECTED')
    with tempfile.TemporaryDirectory(prefix='pip-', dir=tools) as temp:
        path = Path(temp) / wheel['filename']
        path.write_bytes(payload)
        script = "import sys;sys.path.insert(0,sys.argv.pop(1));from pip._internal.cli.main import main;sys.exit(main(sys.argv[1:]))"
        command([python, '-I', '-c', script, str(path), '--isolated', 'install', '--no-index',
                 '--no-deps', '--prefix', str(venv), '--disable-pip-version-check', str(path)], 'PY_BOOTSTRAP', env)


def node_runtime(tools, env):
    local = tools / 'node'
    if local.exists():
        owned(local, True)
        validate_tree(local)
        node, npm = str(local / 'bin/node'), str(local / 'bin/npm')
    else:
        node, npm = shutil.which('node', path=env['PATH']), shutil.which('npm', path=env['PATH'])
    if node and npm:
        candidate = dict(env, PATH=str(Path(node).parent) + ':' + env['PATH'])
        version = command([node, '--version'], 'NODE_CHECK', candidate, check=False)
        if local.exists() and version.returncode:
            raise BuildBlocked(classify(version, 'NODE_CHECK'))
        if version.returncode == 0 and re.fullmatch(rb'v(?:22|24)\.[0-9]+\.[0-9]+\s*', version.stdout):
            npm_version = command([npm, '--version'], 'NPM_VERSION', candidate, tools.parent / 'build-home')
            if not re.fullmatch(rb'[0-9]+\.[0-9]+\.[0-9]+\s*', npm_version.stdout):
                raise BuildBlocked('V2_BUILD_NPM_VERSION_OUTPUT_INVALID')
            if int(npm_version.stdout.split(b'.')[0]) < 9:
                raise BuildBlocked('V2_BUILD_NPM_VERSION_LOCKFILE_UNSUPPORTED')
            print('PASS: V2_NODE_NPM_VERSION node=' + version.stdout.decode().strip()
                  + ' npm=' + npm_version.stdout.decode().strip()
                  + ' scope=' + ('V2_TOOLCHAIN' if local.exists() else 'SYSTEM_READ_ONLY')
                  + ' node_executable=' + node + ' npm_executable=' + npm, flush=True)
            return node, npm, candidate
    if local.exists():
        raise BuildBlocked('V2_BUILD_ISOLATED_NODE_INVALID_NO_OVERWRITE')
    arch = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine())
    if sys.platform != 'linux' or arch is None:
        raise BuildBlocked('V2_BUILD_NODE_PLATFORM_UNSUPPORTED')
    versions = json.loads(download('https://nodejs.org/dist/index.json', 'NODE_DOWNLOAD', 10 * 1024 * 1024))
    matches = [v['version'] for v in versions if v.get('lts') and re.fullmatch(r'v24\.[0-9]+\.[0-9]+', v['version'])]
    if not matches:
        raise BuildBlocked('V2_BUILD_NODE_LTS_UNAVAILABLE')
    version = max(matches, key=lambda v: tuple(map(int, v[1:].split('.'))))
    prefix = f'node-{version}-linux-{arch}'
    filename = prefix + '.tar.gz'
    sums = download(f'https://nodejs.org/dist/{version}/SHASUMS256.txt', 'NODE_DOWNLOAD', 1024 * 1024).decode()
    checksum = next((line.split()[0] for line in sums.splitlines() if len(line.split()) == 2 and line.split()[1] == filename), None)
    payload = download(f'https://nodejs.org/dist/{version}/{filename}', 'NODE_DOWNLOAD')
    if checksum != hashlib.sha256(payload).hexdigest():
        raise BuildBlocked('V2_BUILD_NODE_CHECKSUM_REJECTED')
    with tempfile.TemporaryDirectory(prefix='node-', dir=tools) as temp:
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if not parts or parts[0] != prefix or '..' in parts or Path(member.name).is_absolute():
                    raise BuildBlocked('V2_BUILD_NODE_ARCHIVE_REJECTED')
            tar.extractall(temp, filter='data')
        (Path(temp) / prefix).rename(local)
    return node_runtime(tools, env)


def validate_tree(tree, python_links=False):
    owned(tree, True)
    for current, dirs, files in os.walk(tree, followlinks=False):
        owned(Path(current), True)
        for name in dirs + files:
            path = Path(current) / name
            if path.is_symlink():
                target = path.resolve()
                allowed_python = (python_links and path.parent == tree / 'bin'
                                  and name.startswith('python') and target == Path(sys.executable).resolve())
                if not target.is_relative_to(tree) and not allowed_python:
                    raise BuildBlocked('V2_BUILD_DEPENDENCY_SYMLINK_ESCAPE_REJECTED')
            else:
                owned(path, path.is_dir())


def make_readable(tree):
    """Only managed root-owned dependency/build trees, never app/.local or config."""
    owned(tree, True)
    for current, dirs, files in os.walk(tree, followlinks=False):
        p = Path(current)
        owned(p, True)
        os.chmod(p, 0o755)
        for name in files:
            path = p / name
            if path.is_symlink():
                continue  # venv Python and npm executables legitimately use symlinks.
            owned(path)
            os.chmod(path, 0o755 if path.stat().st_mode & 0o111 else 0o644)


def npm_ready(frontend, npm, env):
    modules = frontend / 'node_modules'
    if not modules.exists():
        return False
    owned(modules, True)
    validate_tree(modules)
    lock = modules / '.package-lock.json'
    if not lock.exists():
        return False
    owned(lock)
    expected = json.loads((frontend / 'package-lock.json').read_text())['packages']
    installed = json.loads(lock.read_text())['packages']
    for path, package in expected.items():
        if not path:
            continue
        if path not in installed:
            if package.get('optional'):
                continue
            return False
        for key in ('version', 'integrity'):
            if package.get(key) != installed[path].get(key):
                return False
    return command([npm, 'ls', '--all', '--json'], 'NPM_TREE', env, frontend, check=False).returncode == 0


def validate_frontend_lock(frontend):
    package = json.loads((frontend / 'package.json').read_text())
    lock = json.loads((frontend / 'package-lock.json').read_text())
    if lock.get('lockfileVersion') not in (2, 3):
        raise BuildBlocked('V2_BUILD_NPM_LOCKFILE_VERSION_UNSUPPORTED')
    root = lock.get('packages', {}).get('')
    if not isinstance(root, dict):
        raise BuildBlocked('V2_BUILD_NPM_LOCKFILE_ROOT_MISSING')
    for key in ('dependencies', 'devDependencies', 'optionalDependencies'):
        if package.get(key, {}) != root.get(key, {}):
            raise BuildBlocked('V2_BUILD_NPM_LOCKFILE_MANIFEST_MISMATCH')


def build(base=BASE, source_digest=None):
    if os.geteuid() != 0:
        raise BuildBlocked('V2_BUILD_ROOT_REQUIRED')
    if sys.version_info < (3, 10):
        raise BuildBlocked('V2_BUILD_PY_RUNTIME_INCOMPATIBLE')
    os.umask(0o077)
    app = base / 'app'
    frontend = app / 'frontend'
    for path, label in ((base, 'BASE'), (app, 'APP'), (app / 'backend', 'BACKEND'), (frontend, 'FRONTEND')):
        owned(path, True, label)
    requirements = app / 'backend/requirements.txt'
    for path in (requirements, frontend / 'package.json', frontend / 'package-lock.json'):
        owned(path)
    if json.loads((frontend / 'package.json').read_text())['scripts']['build'] != 'tsc -b && vite build':
        raise BuildBlocked('V2_BUILD_SCRIPT_REJECTED')
    validate_frontend_lock(frontend)
    for path in (base / 'toolchain', base / 'build-home'):
        private_dir(path)
    prepare_npm_configs(base)
    env = environment(base)
    tools = base / 'toolchain'
    venv = base / 'venv'
    if venv.exists():
        owned(venv, True, 'VENV')
        validate_tree(venv, python_links=True)
    cfg = venv / 'pyvenv.cfg'
    if cfg.exists() or cfg.is_symlink():
        owned(cfg, label='PYVENV_CONFIG')
        current = dict(line.split('=', 1) for line in cfg.read_text().splitlines() if '=' in line)
        if {k.strip(): v.strip().lower() for k, v in current.items()}.get('include-system-site-packages') != 'false':
            raise BuildBlocked('V2_BUILD_VENV_SYSTEM_PACKAGES_REJECTED')
    if not cfg.is_file() or not (venv / 'bin/python').is_file():
        command([sys.executable, '-I', '-m', 'venv', '--without-pip', str(venv)], 'PY_VENV', env)
    owned(venv, True)
    owned(venv / 'bin', True)
    validate_tree(venv, python_links=True)
    owned(venv / 'pyvenv.cfg')
    cfg_values = dict(line.split('=', 1) for line in (venv / 'pyvenv.cfg').read_text().splitlines() if '=' in line)
    cfg_values = {k.strip(): v.strip().lower() for k, v in cfg_values.items()}
    if cfg_values.get('include-system-site-packages') != 'false':
        raise BuildBlocked('V2_BUILD_VENV_SYSTEM_PACKAGES_REJECTED')
    python = str(venv / 'bin/python')
    scope = 'import sys;assert sys.prefix==sys.argv[1] and sys.prefix!=sys.base_prefix'
    command([python, '-I', '-c', scope, str(venv)], 'PY_SCOPE', env)
    pip_bootstrap(venv, tools, env)
    command([python, '-I', '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check',
        '--prefix', str(venv), '--retries', '0', '--timeout', '30', '--only-binary=:all:', '--index-url', 'https://pypi.org/simple',
        '-r', str(requirements)], 'PY_INSTALL', env)
    command([python, '-I', '-m', 'pip', '--isolated', 'check'], 'PY_CHECK', env)
    node, npm, env = node_runtime(tools, env)
    modules = frontend / 'node_modules'
    if modules.exists():
        owned(modules, True, 'NPM_TREE')
    lock_digest = hashlib.sha256((frontend / 'package-lock.json').read_bytes()).hexdigest()
    stamp = tools / 'npm-lock.sha256'
    if stamp.exists() or stamp.is_symlink():
        owned(stamp)
    needs_install = (stamp.exists() and stamp.read_text() != lock_digest) or not npm_ready(frontend, npm, env)
    if needs_install:
        command([npm, 'ci', '--include=dev', '--include=optional', '--ignore-scripts', '--no-audit', '--no-fund',
                 '--fetch-retries=0', '--fetch-timeout=30000'], 'NPM_INSTALL', env, frontend)
    validate_tree(modules)
    stamp.write_text(lock_digest)
    stamp.chmod(0o600)
    dist = frontend / 'dist'
    if dist.exists() or dist.is_symlink():
        owned(dist, True, 'DIST')
        validate_tree(dist)
    command([npm, 'run', 'build'], 'FRONTEND', env, frontend)
    owned(frontend / 'dist', True)
    owned(frontend / 'dist/index.html')
    for tree in (venv, modules, frontend / 'dist'):
        validate_tree(tree, python_links=tree == venv)
        make_readable(tree)
    # Completion marker is written only after dependency checks AND a successful build.
    marker = base / '.completion-built'
    if marker.exists():
        owned(marker)
    if source_digest is None:
        source = base / '.completion-source'
        if source.exists():
            owned(source)
            source_digest = source.read_text()
        else:
            source_digest = lock_digest
    if not re.fullmatch(r'[0-9a-f]{64}', source_digest):
        raise BuildBlocked('V2_BUILD_SOURCE_MARKER_INVALID')
    fd, temp = tempfile.mkstemp(prefix='.build-ready-', dir=base)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(source_digest)
        os.replace(temp, marker)
    finally:
        if Path(temp).exists():
            Path(temp).unlink()
    print('PASS: V2_ISOLATED_DEPENDENCIES_AND_BUILD_READY', flush=True)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 1:
            raise BuildBlocked('V2_BUILD_ARGUMENTS_REJECTED')
        build()
    except BuildBlocked as error:
        print('BLOCKED: ' + error.code, file=sys.stderr)
        sys.exit(1)
    except (PermissionError, FileNotFoundError, OSError) as error:
        code = {errno.ENOSPC: 'DISK_FULL', errno.EACCES: 'PERMISSION_DENIED', errno.EPERM: 'PERMISSION_DENIED',
                errno.ENOENT: 'REQUIRED_PATH_MISSING'}.get(error.errno, 'FILESYSTEM_FAILED')
        print('BLOCKED: V2_BUILD_' + code, file=sys.stderr)
        sys.exit(1)
    except (Exception, KeyboardInterrupt):
        print('BLOCKED: V2_BUILD_METADATA_OR_CHECK_FAILED', file=sys.stderr)
        sys.exit(1)
