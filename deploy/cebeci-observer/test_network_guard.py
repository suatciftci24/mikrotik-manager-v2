"""Offline policy instruction and fail-closed attach tests."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import socket
import struct
import sys
from unittest import TestCase
from unittest.mock import Mock, patch

spec = spec_from_file_location('guard', Path(__file__).with_name('network-guard.py'))
guard = module_from_spec(spec)
spec.loader.exec_module(guard)


def run_policy(name, fields, **endpoint):
    """Execute only the opcodes emitted by the fixed policy."""
    instructions = list(struct.iter_unpack('=BBhi', guard.instructions(name, **endpoint)))
    registers = [0, 100] + [0]*9
    pc = 0
    while True:
        op, regs, offset, immediate = instructions[pc]
        dst, src = regs & 15, regs >> 4
        pc += 1
        if op in (0x61, 0x79):
            registers[dst] = fields.get(registers[src]+offset, 0)
        elif op == 0x55 and registers[dst] != immediate:
            pc += offset
        elif op == 0x56 and registers[dst] & 0xFFFFFFFF != immediate & 0xFFFFFFFF:
            pc += offset
        elif op == 0x15 and registers[dst] == immediate:
            pc += offset
        elif op == 0xb7:
            registers[dst] = immediate
        elif op == 0x95:
            return registers[0]
        elif op not in (0x55, 0x56, 0x15):
            raise AssertionError('Unexpected opcode')


def ipv4(address):
    return int.from_bytes(socket.inet_aton(address), sys.byteorder)


class NetworkGuardTests(TestCase):
    def test_socket_policy_permits_only_ipv4_tcp_stream(self):
        fields = {104:socket.AF_INET, 108:socket.SOCK_STREAM, 112:socket.IPPROTO_TCP}
        self.assertEqual(run_policy('sock_create', fields), 1)
        for offset, forbidden in ((104, socket.AF_INET6), (108, socket.SOCK_DGRAM), (112, 0)):
            self.assertEqual(run_policy('sock_create', {**fields, offset:forbidden}), 0)

    def test_connect_requires_explicit_source_and_exact_destination_and_port(self):
        fields = {104:ipv4('10.250.0.19'), 124:socket.htons(8729), 164:200, 224:ipv4('10.250.0.1')}
        self.assertEqual(run_policy('connect4', fields), 1)
        for offset, forbidden in ((104, ipv4('10.250.0.20')), (124, socket.htons(8728)), (164, 0),
                                  (224, 0), (224, ipv4('10.250.0.2'))):
            self.assertEqual(run_policy('connect4', {**fields, offset:forbidden}), 0)

    def test_distinct_instance_pins_exact_ip_source_and_port(self):
        endpoint = dict(address='10.80.0.222', port=18729, source='10.80.0.200')
        fields = {104:ipv4(endpoint['address']), 124:socket.htons(endpoint['port']),
                  164:200, 224:ipv4(endpoint['source'])}
        self.assertEqual(run_policy('connect4', fields, **endpoint), 1)
        for offset, value in ((104, ipv4('10.80.0.223')), (124, socket.htons(8729)),
                              (224, ipv4('10.80.0.201'))):
            self.assertEqual(run_policy('connect4', {**fields, offset:value}, **endpoint), 0)
        self.assertEqual(run_policy('connect4', fields), 0)

    def test_missing_cgroup_attachment_fails_closed(self):
        def syscall(command, attrs):
            if command == guard.INFO_BY_FD:
                _, _, address = struct.unpack('=IIQ', attrs)
                guard.C.memmove(address, struct.pack('=II', 9, 101), 8)
            return 0, attrs[:24] + bytes(8) if command == guard.PROG_QUERY else attrs

        with patch.object(guard, 'ensure_bpffs'), patch.object(guard, 'observers_cgroup'), \
             patch.object(guard.os, 'open', return_value=10), patch.object(guard.os, 'close'), \
             patch.object(guard, 'obj', return_value=11), patch.object(guard, 'bpf', side_effect=syscall):
            with self.assertRaisesRegex(RuntimeError, '^PROGRAM_NOT_ATTACHED$'):
                guard.verify()

    def test_kernel_load_attributes_include_expected_attach_type_and_cleanup(self):
        load_calls = Mock(return_value=(31, b''))
        with patch.object(guard, 'ensure_bpffs'), patch.object(guard, 'PINS', new=Mock()), \
             patch.object(guard, 'bpf', load_calls), patch.object(guard, 'obj'), patch.object(guard.os, 'close'):
            guard.PINS.__truediv__ = Mock(return_value=Path('/fixture/pin'))
            guard.load()
        for call, attach in zip(load_calls.call_args_list, (2, 10)):
            self.assertEqual(struct.unpack_from('=I', call.args[1], 68)[0], attach)
