#!/usr/bin/env python3
"""Reuse the V2.6.17 pre-IPsec socket guard with one approved endpoint per unit."""
import errno
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import sys

from app.services.router_observation_grants import ROUTER_ID, read_document


def main():
    if os.geteuid() != 0 or len(sys.argv) != 3:
        raise ValueError()
    action, router_id = sys.argv[1:]
    if action not in ('load', 'verify', 'unload') or not re.fullmatch(ROUTER_ID, router_id):
        raise ValueError()
    source = Path(__file__).resolve().parents[1] / 'cebeci-observer' / 'network-guard.py'
    spec = spec_from_file_location('observer_netguard', source)
    guard = module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.PINS = guard.PINS.with_name('mtv2-observer-' + router_id)
    guard.UNIT = 'mikrotik-v2-router-observer@' + router_id + '.service'
    if action == 'load':
        grant = read_document(router_id).grant
        guard.load(address=grant.management_address, port=grant.port, source=grant.source_ip)
    elif action == 'verify':
        guard.verify()
    else:
        guard.unload()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        code = errno.errorcode.get(error.errno, 'IO_ERROR') if isinstance(error, OSError) else 'POLICY_REJECTED'
        print('ROUTER_OBSERVER_NETGUARD_' + code, file=sys.stderr)
        raise SystemExit(1) from None
