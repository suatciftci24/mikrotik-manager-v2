#!/usr/bin/env python3
"""Load and verify two fixed Linux cgroup socket policies. Performs no network I/O."""
import ctypes as C
import errno
import os
from pathlib import Path
import platform
import socket
import stat
import struct
import sys
from contextlib import ExitStack

PINS = Path('/sys/fs/bpf/mtv2-cebeci-guard')
UNIT = 'mikrotik-v2-cebeci-observer.service'
# Stable Linux UAPI values from linux/bpf.h.
PROG_LOAD, OBJ_PIN, OBJ_GET, INFO_BY_FD, PROG_QUERY = 5, 6, 7, 15, 16
PROGRAMS = {'sock_create': (9, 2), 'connect4': (18, 10)}
SYSCALL = {'x86_64': 321, 'aarch64': 280}


def require(value, code):
    if not value:
        raise RuntimeError(code)


def instructions(name):
    """bpf_sock offsets: family/type/protocol/source = 4/8/12/24.
    bpf_sock_addr offsets: user_ip4/user_port/sk = 4/24/64.
    """
    program = []
    guards = []

    def emit(op, dst=0, src=0, off=0, imm=0):
        program.append([op, dst, src, off, imm])

    def guard(op, reg, value):
        guards.append(len(program))
        emit(op, reg, imm=value)

    def field(offset, expected):
        emit(0x61, 2, 1, offset)  # LDX W r2, [r1+offset]
        guard(0x55, 2, expected)  # JNE K -> deny

    def ipv4(address):
        return int.from_bytes(socket.inet_aton(address), sys.byteorder, signed=True)

    if name == 'sock_create':
        field(4, socket.AF_INET)
        field(8, socket.SOCK_STREAM)
        field(12, socket.IPPROTO_TCP)
    elif name == 'connect4':
        field(4, ipv4('10.250.0.19'))
        field(24, socket.htons(8729))
        emit(0x79, 1, 1, 64)   # LDX DW r1, [r1+64]
        guard(0x15, 1, 0)      # JEQ K -> deny if no socket
        field(24, ipv4('10.250.0.1'))
    else:
        raise RuntimeError('PROGRAM_REJECTED')
    emit(0xb7, imm=1)
    emit(0x95)
    deny = len(program)
    emit(0xb7, imm=0)
    emit(0x95)
    for index in guards:
        program[index][3] = deny - index - 1
    return b''.join(struct.pack('=BBhi', op, dst | src << 4, off, imm)
                    for op, dst, src, off, imm in program)


def bpf(command, attributes):
    syscall = SYSCALL.get(platform.machine())
    require(syscall is not None and sys.byteorder == 'little', 'ARCHITECTURE_UNSUPPORTED')
    attributes = (C.c_char * len(attributes)).from_buffer_copy(attributes)
    libc = C.CDLL(None, use_errno=True)
    libc.syscall.restype = C.c_long
    result = libc.syscall(C.c_long(syscall), C.c_int(command), C.byref(attributes), C.c_uint(len(attributes)))
    if result == -1:
        raise OSError(C.get_errno(), f'BPF_COMMAND_{command}')
    return result, bytes(attributes)


def obj(command, path, fd=0):
    name = C.create_string_buffer(os.fsencode(path))
    return bpf(command, struct.pack('=QII', C.addressof(name), fd, 0))[0]


def ensure_bpffs():
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        before, separator, after = line.partition(' - ')
        columns = before.split()
        if separator and len(columns) > 5 and columns[4] == str(PINS.parent) and after.split()[0] == 'bpf':
            return
    raise RuntimeError('BPFFS_NOT_MOUNTED')


def load():
    ensure_bpffs()
    # mkdir is exclusive. A stale or foreign pin tree must never be overwritten.
    PINS.mkdir(mode=0o700)
    created = []
    try:
        for name, (kind, attach) in PROGRAMS.items():
            data = instructions(name)
            insns = C.create_string_buffer(data)
            license_data = C.create_string_buffer(b'GPL')
            attributes = struct.pack('=IIQQIIQII16sII', kind, len(data)//8,
                                     C.addressof(insns), C.addressof(license_data),
                                     0, 0, 0, 0, 0, name.encode(), 0, attach)
            fd = bpf(PROG_LOAD, attributes)[0]
            try:
                obj(OBJ_PIN, PINS/name, fd)
                created.append(PINS/name)
            finally:
                os.close(fd)
    except BaseException:
        for path in created:
            path.unlink()
        PINS.rmdir()
        raise


def unload():
    ensure_bpffs()
    info = PINS.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700,
            'PIN_DIRECTORY_UNSAFE')
    require({p.name for p in PINS.iterdir()} == set(PROGRAMS), 'PIN_CONTENTS_UNSAFE')
    for name in PROGRAMS:
        (PINS/name).unlink()
    PINS.rmdir()


def observers_cgroup():
    line = next((line[3:] for line in Path('/proc/self/cgroup').read_text().splitlines()
                 if line.startswith('0::')), '')
    path = Path(line)
    require(path.is_absolute() and path.name == UNIT and '..' not in path.parts, 'CGROUP_SCOPE_MISMATCH')
    return Path('/sys/fs/cgroup') / path.relative_to('/')


def verify():
    """Systemd can continue on a missing BPFProgram pin. Fail closed in ExecStartPre."""
    ensure_bpffs()
    with ExitStack() as cleanup:
        group = os.open(observers_cgroup(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        cleanup.callback(os.close, group)
        for name, (kind, attach) in PROGRAMS.items():
            pin = obj(OBJ_GET, PINS/name)
            cleanup.callback(os.close, pin)
            info = C.create_string_buffer(8)
            bpf(INFO_BY_FD, struct.pack('=IIQ', pin, len(info), C.addressof(info)))
            actual_kind, program_id = struct.unpack('=II', info.raw)
            require(actual_kind == kind and program_id, 'PIN_TYPE_MISMATCH')
            ids = (C.c_uint32 * 64)()
            query = struct.pack('=IIIIQI4x', group, attach, 0, 0, C.addressof(ids), len(ids))
            _, result = bpf(PROG_QUERY, query)
            count = struct.unpack_from('=I', result, 24)[0]
            require(count <= len(ids) and program_id in ids[:count], 'PROGRAM_NOT_ATTACHED')
    print('CEBECI_NETWORK_GUARD_ATTACHED')


if __name__ == '__main__':
    actions = {'load': load, 'verify': verify, 'unload': unload}
    try:
        require(os.geteuid() == 0 and len(sys.argv) == 2 and sys.argv[1] in actions, 'CLI_REJECTED')
        actions[sys.argv[1]]()
    except OSError as error:
        code = errno.errorcode.get(error.errno, 'IO_ERROR')
        print('CEBECI_NETWORK_GUARD_' + code, file=sys.stderr)
        raise SystemExit(1) from None
    except RuntimeError as error:
        print('CEBECI_NETWORK_GUARD_' + str(error), file=sys.stderr)
        raise SystemExit(1) from None
