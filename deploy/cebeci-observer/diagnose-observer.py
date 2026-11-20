#!/usr/bin/env python3
"""Compare the pinned standalone and systemd observer paths without deploying."""
import argparse
import configparser
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
import errno
import importlib
import io
import json
import logging
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from types import SimpleNamespace

PINS = {'standalone':'da7ef62b6e29703772bb0276f7b8b6cb11a894ac',
        'managed':'433e2ba99a7f4a24ba904b14db98b57f30709f9e'}
UNIT_FILE = 'deploy/cebeci-observer/mikrotik-v2-cebeci-observer.service'
MATERIAL_PATH = Path('.local/cebeci-pilot/v2614-observer')
STEPS = ('RUNTIME', 'AUTHORIZATION', 'SOURCE_BIND', 'TCP', 'SOURCE_PEER', 'TLS', 'LOGIN', 'IDENTITY', 'SNAPSHOT')
CAUSES = {'CONNECTION_UNREACHABLE', 'CONNECTION_TIMEOUT', 'DEADLINE_EXCEEDED', 'CA_CERTIFICATE_REJECTED',
          'TLS_POLICY_REJECTED', 'TLS_VERIFICATION_FAILED', 'CERTIFICATE_PIN_MISMATCH', 'CERTIFICATE_SAN_MISMATCH',
          'ENDPOINT_OR_SOURCE_MISMATCH', 'API_SSL_STOP', 'DEVICE_READ_REJECTED', 'INVALID_TEXT',
          'ROW_LIMIT', 'SENTENCE_LIMIT', 'RESPONSE_BYTE_LIMIT', 'UNEXPECTED_RESPONSE_FIELD',
          'MISSING_RESPONSE_FIELD', 'FIELD_VALUE_LIMIT', 'SENSITIVE_METADATA_REJECTED'}
SECURITY = ('NoNewPrivileges', 'CapabilityBoundingSet', 'ProtectSystem', 'ProtectHome', 'PrivateTmp',
            'PrivateDevices', 'ProtectKernelTunables', 'ProtectKernelModules', 'ProtectControlGroups',
            'RestrictAddressFamilies', 'IPAddressDeny', 'IPAddressAllow', 'LimitCORE', 'UMask',
            'RuntimeDirectoryMode', 'RuntimeDirectoryPreserve', 'TimeoutStopSec')


IMPORTS = (
    ('PYDANTIC_CORE', 'pydantic_core._pydantic_core', 'packages'),
    ('PYDANTIC', 'pydantic', 'packages'),
    ('FASTAPI', 'fastapi', 'packages'),
    ('OBSERVER', 'app.adapters.cebeci_observer', 'source'),
    ('TRANSPORT', 'app.adapters.router_api_ssl', 'source'),
    ('WIRE', 'app.adapters.cebeci_api_ssl', 'source'),
    ('COLLECTOR', 'app.adapters.device_inventory', 'source'),
    ('SNAPSHOT_SCHEMA', 'app.schemas.device_inventory', 'source'),
    ('SNAPSHOT_WRITER', 'app.services.device_poller', 'source'),
)
KNOWN_MODULES = {
    'app': 'APP', 'pydantic_core': 'PYDANTIC_CORE', 'pydantic': 'PYDANTIC', 'fastapi': 'FASTAPI',
    'starlette': 'STARLETTE', 'anyio': 'ANYIO', 'typing_extensions': 'TYPING_EXTENSIONS',
    'typing_inspection': 'TYPING_INSPECTION', 'annotated_types': 'ANNOTATED_TYPES',
    'annotated_doc': 'ANNOTATED_DOC', 'typing': 'TYPING_STDLIB', '_ssl': 'SSL_STDLIB',
}
IMPORT_FAILURES = {'MODULE_MISSING', 'NATIVE_MAP_DENIED', 'NATIVE_ABI_MISMATCH', 'NATIVE_LIBRARY_MISSING',
                   'NATIVE_INIT_FAILED', 'IMPORT_SYMBOL_MISSING', 'IMPORT_ERROR', 'ACCESS_DENIED', 'PATH_MISSING',
                   'IO_ERROR', 'MODULE_INIT_FAILED', 'ORIGIN_REJECTED'}


class Stop(RuntimeError):
    pass


class TCPMeasured(BaseException):
    pass


def need(condition, code):
    if not condition:
        raise Stop(code)


def command(*args, timeout=20, cwd=None):
    with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True, cwd=cwd) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def emit(step, status):
    print(f'{step}={status}', flush=True)


def import_failure(error):
    if isinstance(error, ModuleNotFoundError):
        return 'MODULE_MISSING', KNOWN_MODULES.get((error.name or '').partition('.')[0])
    if isinstance(error, ImportError):
        # Native loader messages are classified locally and never printed.
        detail = str(error).lower()
        if 'failed to map segment' in detail or 'cannot map' in detail:
            return 'NATIVE_MAP_DENIED', None
        if any(marker in detail for marker in ('wrong elf class', 'invalid elf', 'undefined symbol', 'glibc_')):
            return 'NATIVE_ABI_MISMATCH', None
        if 'cannot open shared object file' in detail:
            return 'NATIVE_LIBRARY_MISSING', None
        if 'module export function' in detail:
            return 'NATIVE_INIT_FAILED', None
        if 'cannot import name' in detail:
            return 'IMPORT_SYMBOL_MISSING', None
        return 'IMPORT_ERROR', None
    if isinstance(error, PermissionError):
        return 'ACCESS_DENIED', None
    if isinstance(error, FileNotFoundError):
        return 'PATH_MISSING', None
    if isinstance(error, OSError):
        return 'IO_ERROR', None
    return 'MODULE_INIT_FAILED', None


def load_runtime(root, packages):
    source = root/'backend'
    need(sys.flags.isolated and sys.flags.no_site, 'PYTHON_ISOLATION_REQUIRED')
    need(Path.cwd() == root, 'WORKING_DIRECTORY_MISMATCH')
    for directory, code in ((source, 'SOURCE_DIRECTORY_ACCESS'), (packages, 'PACKAGE_DIRECTORY_ACCESS')):
        try:
            with os.scandir(directory) as entries:
                next(entries, None)
            need(os.access(directory, os.X_OK), code)
        except OSError:
            raise Stop(code) from None
    try:
        with (source/'app/adapters/cebeci_observer.py').open('rb') as stream:
            stream.read(1)
    except OSError:
        raise Stop('SOURCE_MODULE_ACCESS') from None
    need(not os.statvfs(packages).f_flag & os.ST_NOEXEC, 'PACKAGE_FILESYSTEM_NOEXEC')
    sys.path[:0] = [str(source), str(packages)]
    loaded = {}
    for label, module_name, location in IMPORTS:
        try:
            module = importlib.import_module(module_name)
            allowed = source if location == 'source' else packages
            origin = getattr(module, '__file__', None)
            need(origin and Path(origin).resolve().is_relative_to(allowed), 'ORIGIN_REJECTED')
            loaded[label] = module
        except Stop:
            print(f'IMPORT={label}:ORIGIN_REJECTED', flush=True)
            raise Stop('IMPORT_FAILED') from None
        except Exception as error:
            reason, missing = import_failure(error)
            suffix = ':' + missing if missing else ''
            print(f'IMPORT={label}:{reason}{suffix}', flush=True)
            raise Stop('IMPORT_FAILED') from None
    return loaded


def worker(root, packages, mode, runtime, network_trace=False):
    logging.disable(logging.CRITICAL)
    try:
        loaded = load_runtime(root, packages)
    except Stop as error:
        emit('RUNTIME', str(error))
        return 1
    observer, transport = loaded['OBSERVER'], loaded['TRANSPORT']
    ApiSslStop, _Wire = loaded['WIRE'].ApiSslStop, loaded['WIRE']._Wire
    DeviceReadWire = loaded['COLLECTOR'].DeviceReadWire
    DeviceInventory = loaded['SNAPSHOT_SCHEMA'].DeviceInventory
    _publish = loaded['SNAPSHOT_WRITER']._publish

    emit('RUNTIME', 'PASS')
    current = 'AUTHORIZATION'
    identity_failure = None

    def advance(stage):
        nonlocal current
        current = stage

    class ProbeSocket(socket.socket):
        def bind(self, address):
            advance('SOURCE_BIND')
            try:
                super().bind(address)
            except OSError as error:
                if error.errno == errno.EADDRNOTAVAIL:
                    emit('SOURCE_BIND', 'ADDRESS_NOT_AVAILABLE')
                elif error.errno in (errno.EACCES, errno.EPERM):
                    emit('SOURCE_BIND', 'PERMISSION')
                raise
            emit('SOURCE_BIND', 'PASS')

        def connect(self, address):
            advance('TCP')
            if network_trace:
                with (runtime/'probe-port').open('x') as marker:
                    marker.write(str(self.getsockname()[1]))
                until(lambda: (root/'network-go').is_file(), 18, 'TRACE_GATE_TIMEOUT')
            try:
                super().connect(address)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EPERM):
                    emit('TCP', 'PERMISSION')
                raise
            emit('TCP', 'PASS')
            if network_trace:
                raise TCPMeasured

    class ProbeTLS:
        def __init__(self, context):
            self.context = context

        def __getattr__(self, key):
            return getattr(self.context, key)

        def wrap_socket(self, raw, **kwargs):
            advance('TLS')
            return self.context.wrap_socket(raw, **kwargs)

    def new_socket(*args, **kwargs):
        advance('SOURCE_BIND')
        return ProbeSocket(*args, **kwargs)

    transport.socket = SimpleNamespace(socket=new_socket, AF_INET=socket.AF_INET, SOCK_STREAM=socket.SOCK_STREAM)
    original_context = transport.verified_tls_context
    transport.verified_tls_context = lambda *args: ProbeTLS(original_context(*args))
    original_login = _Wire.login
    original_read = DeviceReadWire.fixed_read
    original_transport = transport.RouterApiSslClient._verified_read

    def login(wire, **kwargs):
        # The real transport checks peer/source, TLS, IP SAN and leaf pin before invoking login.
        emit('SOURCE_PEER', 'PASS')
        emit('TLS', 'PASS')
        advance('LOGIN')
        result = original_login(wire, **kwargs)
        emit('LOGIN', 'PASS')
        advance('IDENTITY')
        return result

    def read_step(wire, menu):
        nonlocal identity_failure
        if menu in ('/ppp/secret', '/ppp/active') and current == 'IDENTITY':
            emit('IDENTITY', 'PASS')
            advance('SNAPSHOT')
        result = original_read(wire, menu)
        if menu in ('/system/identity', '/system/resource') and len(result) != 1:
            identity_failure = 'ROW_COUNT_MISMATCH'
        elif menu == '/system/identity' and result[0].get('name') != observer.IDENTITY:
            identity_failure = 'NAME_MISMATCH'
        elif menu == '/system/resource' and identity_failure is None:
            if result[0].get('board-name') != observer.MODEL:
                identity_failure = 'MODEL_MISMATCH'
            elif (result[0].get('version') or '').removesuffix(' (stable)') != observer.VERSION:
                identity_failure = 'VERSION_MISMATCH'
        return result

    def capture_error(client, *args):
        try:
            return original_transport(client, *args)
        except ApiSslStop as error:
            code = str(error).partition(':')[0]
            category = code if code in CAUSES else ('AUTHENTICATION_REJECTED' if code.startswith('AUTHENTICATION')
                                                     else 'REJECTED')
            if code == 'ENDPOINT_OR_SOURCE_MISMATCH':
                advance('SOURCE_PEER')
            if current == 'IDENTITY' and code == 'DEVICE_READ_REJECTED' and identity_failure:
                category = identity_failure
            emit(current, category)
            raise

    _Wire.login = login
    DeviceReadWire.fixed_read = read_step
    transport.RouterApiSslClient._verified_read = capture_error
    try:
        expiry = observer.managed_expiry() if mode == 'managed' else None
        sample = observer.make_sampler(managed=True) if mode == 'managed' else observer.make_sampler()
        emit('AUTHORIZATION', 'PASS')
        advance('TLS')
        result = sample(previous=None)
        if network_trace:
            return 1
        advance('SNAPSHOT')
        output = runtime if mode == 'managed' else root/MATERIAL_PATH
        fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            directory = os.fstat(fd)
            need(stat.S_IMODE(directory.st_mode) == (0o750 if mode == 'managed' else 0o700)
                 and directory.st_uid == os.geteuid() and directory.st_gid == os.getegid(),
                 'DIRECTORY_METADATA')
            if mode == 'managed':
                expiry = min(expiry, observer.managed_expiry())
                _publish(fd, result, expiry)
            else:
                _publish(fd, result)
        finally:
            os.close(fd)
        path = output/'device-inventory.json'
        info = path.stat()
        expected_mode = 0o640 if mode == 'managed' else 0o600
        need(stat.S_IMODE(info.st_mode) == expected_mode and info.st_uid == os.geteuid()
             and info.st_gid == os.getegid() and info.st_nlink == 1, 'FILE_METADATA')
        snapshot = DeviceInventory.model_validate_json(path.read_bytes())
        need(len(snapshot.routers) == 1 and snapshot.routers[0] == result, 'PAYLOAD_MISMATCH')
        emit('SNAPSHOT', result.error or 'PASS')
        if result.connection == 'ONLINE' and result.error is None:
            emit('ACCOUNTS', f'{len(result.accounts or [])},COMPLETE={str(result.accounts_complete).upper()}')
            return 0
    except TCPMeasured:
        return 0
    except Stop as error:
        emit(current, str(error))
    except (OSError, ValueError, ApiSslStop):
        emit(current, 'LOCAL_OR_VALIDATION_FAILURE')
    return 1


def pinned_sources(repo, workspace, modes=PINS):
    unit = None
    for mode in modes:
        pin = PINS[mode]
        args = ('backend/app', UNIT_FILE) if mode == 'managed' else ('backend/app',)
        archive = command('git', '-c', 'safe.directory='+str(repo), '-C', str(repo), 'archive', pin,
                          '--', *args)
        need(archive.returncode == 0, f'{mode.upper()}_PIN_UNAVAILABLE')
        root = workspace/mode
        root.mkdir(mode=0o755)
        root.chmod(0o755)
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as payload:
            need(all(member.isfile() or member.isdir() for member in payload), 'SOURCE_ARCHIVE_UNSAFE')
            payload.extractall(root, filter='data')
        for path in (root/'backend').rglob('*'):
            path.chmod(0o755 if path.is_dir() else 0o644)
        (root/'backend').chmod(0o755)
        if mode == 'managed':
            unit = configparser.ConfigParser(interpolation=None)
            unit.read(root/UNIT_FILE)
    need(unit is not None and all(key in unit['Service'] for key in SECURITY), 'MANAGED_POLICY_UNAVAILABLE')
    return unit['Service']


def read_existing(path, uid, limit):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_uid == uid and info.st_nlink == 1
             and stat.S_IMODE(info.st_mode) in (0o400, 0o600) and 0 < info.st_size <= limit,
             'PRIVATE_MATERIAL_REJECTED')
        data = stream.read(limit+1)
    need(0 < len(data) <= limit, 'PRIVATE_MATERIAL_REJECTED')
    return data


def stage_material(root, account, material):
    directory = root
    for part in MATERIAL_PATH.parts:
        directory /= part
        directory.mkdir(mode=0o700)
        os.chown(directory, account.pw_uid, account.pw_gid)
    approval = dict(scope='V2614_CEBECI_TOWERS_READ_ONLY',
                    expires_at=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
    for name, data in (*material.items(), ('approval.json', json.dumps(approval).encode())):
        with (directory/name).open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            os.fchown(stream.fileno(), account.pw_uid, account.pw_gid)
            stream.write(data)


def report(mode, result):
    passed = set()
    safe = CAUSES | {'PASS', 'ADDRESS_NOT_AVAILABLE', 'PERMISSION', 'AUTHENTICATION_REJECTED', 'REJECTED',
                     'ROW_COUNT_MISMATCH', 'NAME_MISMATCH', 'MODEL_MISMATCH', 'VERSION_MISMATCH',
                     'DIRECTORY_METADATA', 'FILE_METADATA', 'PAYLOAD_MISMATCH', 'LOCAL_OR_VALIDATION_FAILURE',
                     'TRACE_GATE_TIMEOUT', 'IMPORT_FAILED', 'RUNTIME_IO_FAILURE', 'PYTHON_ISOLATION_REQUIRED', 'WORKING_DIRECTORY_MISMATCH',
                     'SOURCE_DIRECTORY_ACCESS', 'PACKAGE_DIRECTORY_ACCESS', 'SOURCE_MODULE_ACCESS',
                     'PACKAGE_FILESYSTEM_NOEXEC',
                     'UNREACHABLE', 'TIMEOUT', 'TLS', 'AUTHORIZATION', 'INVALID_DATA'}
    import_labels = {label for label, _, _ in IMPORTS}
    for line in result.stdout.decode(errors='replace').splitlines():
        stage, _, value = line.partition('=')
        if stage == 'IMPORT':
            check, _, failure = value.partition(':')
            reason, _, module = failure.partition(':')
            if check in import_labels and reason in IMPORT_FAILURES and (not module or module in KNOWN_MODULES.values()):
                print(f'{mode.upper()} {line}')
        if stage in STEPS and value in safe or re.fullmatch(r'ACCOUNTS=[0-9]{1,3},COMPLETE=(?:TRUE|FALSE)', line):
            print(f'{mode.upper()} {line}')
            passed.add(stage)
    for stage in STEPS:
        if stage not in passed:
            print(f'{mode.upper()} {stage}=NOT_REACHED')
    if result.returncode:
        print(f'{mode.upper()} EXIT={result.returncode}')


def until(check, seconds, failure):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.05)
    raise Stop(failure)


@contextmanager
def capture_process(args, stdout, stderr):
    with stdout.open('wb') as output, stderr.open('wb') as errors:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                   start_new_session=True, env={**os.environ, 'LC_ALL':'C'})
        try:
            yield process
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)


def trace_mount():
    for path in (Path('/sys/kernel/tracing'), Path('/sys/kernel/debug/tracing')):
        event = path/'events/skb/kfree_skb/format'
        if event.is_file():
            data = event.read_text()
            need(re.search(r'field:[^;]*\breason;', data), 'DROP_REASON_UNAVAILABLE')
            names = {int(number):name for number, name in re.findall(r'\{\s*(\d+)\s*,\s*"([A-Z0-9_]+)"\s*\}', data)}
            need(any('BPF_CGROUP' in name for name in names.values()), 'BPF_DROP_REASON_NAMES_UNAVAILABLE')
            need((path/'events/skb/consume_skb/format').is_file(), 'CONSUME_TRACEPOINT_UNAVAILABLE')
            return names
    raise Stop('TRACEFS_UNAVAILABLE')


def bpf_program(pid, port):
    # Filter on the worker socket and on the exact reverse tuple for skb events
    # before TCP associates an incoming packet with its socket.
    source = int.from_bytes(socket.inet_aton('10.250.0.1'), sys.byteorder)
    target = int.from_bytes(socket.inet_aton('10.250.0.19'), sys.byteorder)
    service = socket.htons(8729)
    local = socket.htons(port)
    return fr"""
BEGIN {{ printf("READY\n"); }}
kprobe:tcp_v4_connect /pid == {pid}/ {{ @sock[(uint64)arg0] = 1; printf("SOCKET\n"); }}
kprobe:xfrm_output /@sock[(uint64)arg0]/ {{
    @transform[(uint64)arg1] = 1; @xfrm_thread[tid] = 1; printf("XFRM_ENTER\n");
}}
kretprobe:xfrm_output /@xfrm_thread[tid]/ {{
    printf("XFRM_RETURN %lld\n", (int64)(int32)retval); delete(@xfrm_thread[tid]);
}}
tracepoint:skb:kfree_skb {{
    $address = (uint64)args->skbaddr;
    $skb = (struct sk_buff *)args->skbaddr;
    $transformed = @transform[$address];
    $related = @sock[(uint64)$skb->sk] || $transformed;
    $reverse = 0;
    $outer_ipv4 = 0;
    if ($skb->network_header != 65535) {{
        $ip = (struct iphdr *)($skb->head + $skb->network_header);
        if ($transformed && $ip->version == 4 && ($ip->protocol == 50 || $ip->protocol == 17) &&
            $ip->daddr != {target}) {{ $outer_ipv4 = 1; }}
        if (!$related && $ip->version == 4 && $ip->ihl >= 5 && $ip->protocol == 6 &&
            $ip->saddr == {target} && $ip->daddr == {source}) {{
            $tcp = (struct tcphdr *)((uint64)$ip + 4 * $ip->ihl);
            $reverse = $tcp->source == {service} && $tcp->dest == {local};
        }}
    }}
    if ($related || $reverse) {{
        printf("DROP %u %u %u %u\n", args->reason, $transformed, $reverse, $outer_ipv4);
    }}
    if ($transformed) {{ delete(@transform[$address]); }}
}}
tracepoint:skb:consume_skb /@transform[(uint64)args->skbaddr]/ {{ delete(@transform[(uint64)args->skbaddr]); }}
END {{ clear(@sock); clear(@transform); clear(@xfrm_thread); }}
"""


def hook_types(cgroup):
    require_path = Path('/sys/fs/cgroup') / cgroup.removeprefix('/')
    allowed = {'cgroup_inet_ingress', 'cgroup_inet_egress', 'cgroup_inet4_connect', 'cgroup_inet4_bind',
               'ingress', 'egress', 'connect4', 'bind4'}
    for label, options in (('LOCAL', ()), ('EFFECTIVE', ('effective',))):
        result = command('bpftool', '-j', 'cgroup', 'show', str(require_path), *options)
        try:
            hooks = json.loads(result.stdout) if not result.returncode else None
        except ValueError:
            hooks = None
        if not isinstance(hooks, list):
            print(f'CGROUP_HOOKS_{label}=UNAVAILABLE')
            continue
        safe = []
        for item in hooks:
            if isinstance(item, dict):
                kind = item.get('attach_type', item.get('attach_type_name', ''))
                program = item.get('id')
                name = kind if isinstance(kind, str) and kind in allowed else 'OTHER'
                safe.append(f'{name}:{program}' if type(program) is int and program > 0 else name)
        print(f'CGROUP_HOOKS_{label}=' + (','.join(sorted(safe)) or 'NONE'))


def summarize_network(events, packets, names, port):
    counts = {}
    source = f'10.250.0.1.{port}'
    target = '10.250.0.19.8729'
    for line in packets.splitlines():
        if f'{source} > {target}: Flags [S]' in line:
            counts['INNER_SYN'] = counts.get('INNER_SYN', 0) + 1
        elif f'{target} > {source}: Flags [S.]' in line:
            counts['INNER_SYN_ACK'] = counts.get('INNER_SYN_ACK', 0) + 1
    for key in ('INNER_SYN', 'INNER_SYN_ACK'):
        print(f'{key}={counts.get(key, 0)}')
    confirmed = set()
    saw_socket = False
    for line in events.splitlines():
        if line == 'SOCKET':
            saw_socket = True
        elif line == 'XFRM_ENTER' or re.fullmatch(r'XFRM_RETURN -?[0-9]{1,19}', line):
            print(line.replace(' ', '=', 1))
        elif match := re.fullmatch(r'DROP ([0-9]{1,10}) ([01]) ([01]) ([01])', line):
            number, after_xfrm_enter, reverse, outer = map(int, match.groups())
            reason = names.get(number, f'REASON_{number}')
            print(f'PACKET_DROP={reason},XFRM_ENTERED={after_xfrm_enter},REVERSE_TUPLE={reverse},OUTER_IPV4={outer}')
            if 'BPF_CGROUP' in reason:
                confirmed.add('BPF_OUTER_IPV4_DROP' if outer else ('BPF_AFTER_XFRM_ENTRY' if after_xfrm_enter else 'BPF_DROP'))
            elif 'XFRM' in reason or 'IPSEC' in reason:
                confirmed.add('XFRM_DROP')
    print('KERNEL_FLOW_TRACKING=' + ('SEEN' if saw_socket else 'NOT_SEEN'))
    print('ATTRIBUTION=' + (','.join(sorted(confirmed)) or 'INCONCLUSIVE'))


def network_probe(unit, runtime, root, workspace, unit_args):
    names = trace_mount()
    need(Path('/sys/kernel/btf/vmlinux').is_file(), 'KERNEL_BTF_UNAVAILABLE')
    for tool in ('tcpdump', 'bpftrace', 'bpftool'):
        need(shutil.which(tool), 'TRACE_TOOL_MISSING_' + tool.upper())
    port = None
    pstdout, pstderr = workspace/'managed.out', workspace/'managed.err'
    bout, berr = workspace/'bpf.out', workspace/'bpf.err'
    tout, terr = workspace/'tcp.out', workspace/'tcp.err'
    try:
        with capture_process(unit_args, pstdout, pstderr) as managed:
            def port_ready():
                if managed.poll() is not None:
                    raise Stop('MANAGED_EXIT_BEFORE_TCP')
                try:
                    with os.fdopen(os.open(runtime/'probe-port', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as marker:
                        data = marker.read(8).strip()
                    return int(data) if re.fullmatch(rb'[0-9]{1,5}', data) and 0 < int(data) <= 65535 else None
                except FileNotFoundError:
                    return None

            port = until(port_ready, 10, 'MANAGED_TCP_GATE_NOT_REACHED')
            details = command('systemctl', 'show', '-p', 'MainPID', '-p', 'ControlGroup', '--', unit)
            props = dict(line.split('=', 1) for line in details.stdout.decode().splitlines() if '=' in line)
            pid, cgroup = props.get('MainPID', ''), props.get('ControlGroup', '')
            need(details.returncode == 0 and pid.isdigit() and int(pid) > 0 and cgroup.startswith('/')
                 and '..' not in Path(cgroup).parts and Path(cgroup).name == unit, 'MANAGED_CGROUP_UNVERIFIED')
            hook_types(cgroup)
            script = workspace/'trace.bt'
            script.write_text(bpf_program(int(pid), port))
            tuple_filter = (f'(src host 10.250.0.1 and src port {port} and dst host 10.250.0.19 and dst port 8729)'
                            f' or (src host 10.250.0.19 and src port 8729 and dst host 10.250.0.1 and dst port {port})')
            with ExitStack() as stack:
                capture = stack.enter_context(capture_process(
                    ('tcpdump', '-l', '-nn', '-i', 'any', '-p', '-s', '64', '-c', '32',
                     f'ip and tcp and (tcp[13] & 2 != 0) and ({tuple_filter})'), tout, terr))
                tracing = stack.enter_context(capture_process(('bpftrace', '-q', '-B', 'line', str(script)), bout, berr))

                def ready():
                    need(capture.poll() is None, 'TCP_CAPTURE_START_FAILED')
                    if tracing.poll() is not None:
                        errors = berr.read_bytes().lower()
                        for fragment, code in ((b'permission denied', 'TRACE_PERMISSION'),
                                               (b'operation not permitted', 'TRACE_PERMISSION'),
                                               (b'verifier', 'TRACE_VERIFIER_REJECTED'),
                                               (b'not traceable', 'TRACE_SYMBOL_UNAVAILABLE'),
                                               (b'unknown struct', 'TRACE_KERNEL_TYPES_UNAVAILABLE')):
                            if fragment in errors:
                                raise Stop(code)
                        raise Stop('KERNEL_TRACE_START_FAILED')
                    return b'listening on' in terr.read_bytes() and b'READY\n' in bout.read_bytes()

                until(ready, 8, 'TRACE_NOT_READY')
                (root/'network-go').touch()
                managed.wait(timeout=14)
    finally:
        command('systemctl', 'stop', unit)
        need(not os.path.lexists(runtime), 'DIAGNOSTIC_RUNTIME_CLEANUP_UNVERIFIED')
        if pstdout.exists():
            report('managed', subprocess.CompletedProcess([], managed.poll() or 0, pstdout.read_bytes(), b''))
        if port is not None and bout.exists() and tout.exists():
            summarize_network(bout.read_text(errors='replace'), tout.read_text(errors='replace'), names, port)
    return int(managed.returncode != 0)


def launch(args):
    need(os.geteuid() == 0, 'ROOT_REQUIRED')
    # Reject an active production observer, so this only runs after rollback.
    active = command('systemctl', 'is-active', 'mikrotik-v2-cebeci-observer.service')
    need(active.returncode in (3, 4) and active.stdout.strip() in (b'inactive', b'failed', b'unknown'),
         'LIVE_OBSERVER_STATE_UNSAFE')
    repo = Path(args.repo).resolve(strict=True)
    private = Path(args.material)
    need(private.is_absolute() and private.resolve(strict=True) == private and
         private.parts[-3:] == MATERIAL_PATH.parts, 'MATERIAL_DIRECTORY_REJECTED')
    info = private.stat()
    need(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid != 0,
         'MATERIAL_DIRECTORY_REJECTED')
    account = pwd.getpwuid(info.st_uid)
    need(account.pw_gid != 0, 'OBSERVER_GROUP_REJECTED')
    material = {name:read_existing(private/name, account.pw_uid, limit)
                for name, limit in (('ca.pem', 262144), ('password', 1024))}
    version = f'python{sys.version_info.major}.{sys.version_info.minor}'
    packages = Path(args.venv).resolve(strict=True)/'lib'/version/'site-packages'
    need(packages.is_dir(), 'VENV_PYTHON_ABI_OR_PACKAGES_MISSING')
    original_mount = 'NOEXEC' if os.statvfs('/run').f_flag & os.ST_NOEXEC else 'EXEC_ALLOWED'
    print(f'ORIGINAL_RUN_MOUNT={original_mount}')
    os.umask(0o077)
    status = []
    with tempfile.TemporaryDirectory(prefix='mtv2-cebeci-diag-', dir='/opt') as directory:
        workspace = Path(directory)
        workspace.chmod(0o755)
        modes = ('managed',) if args.managed_network else tuple(PINS)
        props = pinned_sources(repo, workspace, modes)
        # Copy dependencies only. Keep paths outside ProtectHome and avoid running pip.
        target = workspace/'packages'
        need(not any(path.is_symlink() for path in packages.rglob('*')), 'VENV_PACKAGE_LINK_REJECTED')
        shutil.copytree(packages, target, ignore=shutil.ignore_patterns('__pycache__', '*.pth'))
        for path in target.rglob('*'):
            path.chmod(0o755 if path.is_dir() else 0o644)
        target.chmod(0o755)
        launcher = workspace/'probe.py'
        shutil.copyfile(Path(__file__), launcher)
        launcher.chmod(0o644)
        unit = workspace.name + '.service'
        runtime = Path('/run')/(workspace.name+'-snapshot')
        for mode in modes:
            stage_material(workspace/mode, account, material)
        del material
        need(not os.path.lexists(runtime), 'DIAGNOSTIC_RUNTIME_EXISTS')
        for mode in modes:
            root = workspace/mode
            worker_args = ('/usr/bin/python3', '-I', '-S', '-B', str(launcher), '--worker', str(root),
                           str(target), mode, str(runtime))
            if args.managed_network:
                options = [f'--property={key}={props[key]}' for key in SECURITY]
                return network_probe(unit, runtime, root, workspace,
                    ('systemd-run', '--quiet', '--wait', '--pipe', '--collect', f'--unit={unit}',
                     f'--uid={account.pw_uid}', f'--gid={account.pw_gid}', f'--working-directory={root}',
                     f'--property=RuntimeDirectory={runtime.name}', '--property=RuntimeMaxSec=40s',
                     *options, *worker_args, '--managed-network'))
            if mode == 'standalone':
                try:
                    result = command('runuser', '-u', account.pw_name, '--', 'env', '-i',
                                     'PATH=/usr/bin:/bin', *worker_args, timeout=25, cwd=root)
                except subprocess.TimeoutExpired:
                    result = subprocess.CompletedProcess(worker_args, 124, b'', b'')
            else:
                options = [f'--property={key}={props[key]}' for key in SECURITY]
                try:
                    result = command('systemd-run', '--quiet', '--wait', '--pipe', '--collect',
                                     f'--unit={unit}', f'--uid={account.pw_uid}', f'--gid={account.pw_gid}',
                                     f'--working-directory={root}', f'--property=RuntimeDirectory={runtime.name}',
                                     '--property=RuntimeMaxSec=30s', *options, *worker_args, timeout=45)
                except subprocess.TimeoutExpired:
                    result = subprocess.CompletedProcess(worker_args, 124, b'', b'')
                finally:
                    command('systemctl', 'stop', unit)
                    need(not os.path.lexists(runtime), 'DIAGNOSTIC_RUNTIME_CLEANUP_UNVERIFIED')
            report(mode, result)
            status.append(result.returncode)
    return int(any(status))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='/srv/mikrotik-v26-next')
    parser.add_argument('--material')
    parser.add_argument('--venv')
    parser.add_argument('--managed-network', action='store_true', help='trace only the managed TCP connection')
    parser.add_argument('--worker', nargs=4, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        root, packages, mode, runtime = args.worker
        if args.managed_network and mode != 'managed':
            return 1
        try:
            return worker(Path(root), Path(packages), mode, Path(runtime), args.managed_network)
        except OSError:
            emit('RUNTIME', 'RUNTIME_IO_FAILURE')
            return 1
    try:
        need(args.material and args.venv, 'MATERIAL_AND_VENV_REQUIRED')
        return launch(args)
    except Stop as error:
        print(f'DIAGNOSTIC={error}', file=sys.stderr)
    except (OSError, KeyError, ValueError, subprocess.SubprocessError):
        print('DIAGNOSTIC=LOCAL_EXECUTION_FAILED', file=sys.stderr)
    return 1


if __name__ == '__main__':
    for sig in (signal.SIGINT, signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, lambda *_: (_ for _ in ()).throw(Stop('INTERRUPTED')))
    raise SystemExit(main())
