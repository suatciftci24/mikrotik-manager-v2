"""Operator CLI for offline grant management. It never calls a router."""
import argparse
import fcntl
from getpass import getpass
import grp
import json
import os
import pwd
import re
import sys
from uuid import uuid4

from app.adapters.cebeci_api_ssl import ApiSslStop
from app.integrations.cebeci_access import verified_tls_context
from app.router_observer import observer_vault
from app.services.router_observation_grants import (
    GROUP, MAX_GRANT_BYTES, MAX_ROUTERS, ROUTER_ID, USER, GrantDocument, Scope,
    open_grants, read_document, registry_material,
)


def export_registry(router_id):
    from app.core.database import SessionLocal
    from app.models.router_registry import RegisteredRouter

    with SessionLocal() as session:
        row = session.get(RegisteredRouter, router_id)
        if row is None:
            raise ValueError('OBSERVATION_ROUTER_NOT_FOUND')
        print(json.dumps(registry_material(row)))


def approve(directory, router_id, payload, replace=False):
    if set(payload) - {'credential_ref', 'read_only_username', 'router', 'wan_interface', 'reviewed_connection'}:
        raise ValueError('OBSERVATION_INPUT_REJECTED')
    router = dict(payload['router'])
    if router.pop('pending_verification'):
        # Pending inventory contributes the endpoint and registration ID only.
        reviewed = payload['reviewed_connection']
        keys = {'source_ip', 'leaf_sha256', 'identity', 'model', 'routeros_version', 'trust'}
        if set(reviewed) != keys or set(router) & keys:
            raise ValueError('OBSERVATION_REVIEW_REJECTED')
        router.update(reviewed)
    elif 'reviewed_connection' in payload:
        raise ValueError('OBSERVATION_VERIFIED_MATERIAL_OVERRIDE')
    trust = router.pop('trust')
    document = GrantDocument.model_validate({'trust': trust, 'grant': {
        **router, 'scope': 'ROUTEROS_READ_ONLY', 'grant_id': uuid4().hex,
        'credential_ref': payload['credential_ref'], 'read_only_username': payload['read_only_username'],
        'wan_interface': payload.get('wan_interface'),
    }})
    grant = document.grant
    if grant.router_id != router_id:
        raise ValueError('OBSERVATION_ROUTER_ID_REJECTED')
    Scope(grant.management_address, grant.source_ip, grant.port).policy()
    verified_tls_context(document.trust.ca_pem)
    name = router_id + '.json'
    entries = [entry for entry in os.listdir(directory) if re.fullmatch(ROUTER_ID + r'\.json', entry)]
    if name in entries and not replace:
        raise ValueError('OBSERVATION_GRANT_ALREADY_EXISTS')
    if name not in entries and len(entries) >= MAX_ROUTERS:
        raise ValueError('OBSERVATION_ROUTER_CAPACITY')
    for entry in entries:
        if entry == name:
            continue
        other = read_document(entry.removesuffix('.json'), directory=directory).grant
        if (other.management_address, other.port) == (grant.management_address, grant.port):
            raise ValueError('OBSERVATION_ENDPOINT_EXISTS')
        if other.credential_ref == grant.credential_ref:
            raise ValueError('OBSERVATION_CREDENTIAL_ALREADY_ASSIGNED')
    raw = document.model_dump_json().encode()
    if len(raw) > MAX_GRANT_BYTES:
        raise ValueError('OBSERVATION_GRANT_SIZE_REJECTED')
    temporary = '.grant-' + uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchown(stream.fileno(), 0, grp.getgrnam(GROUP).gr_gid)
            os.fchmod(stream.fileno(), 0o640)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def revoke(directory, router_id):
    try:
        os.unlink(router_id + '.json', dir_fd=directory)
        os.fsync(directory)
    except FileNotFoundError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('export-registry', 'approve', 'revoke'):
        command = commands.add_parser(name)
        command.add_argument('router_id')
        if name != 'export-registry':
            command.add_argument('--confirm', required=True, action='store_true')
        if name == 'approve':
            command.add_argument('--replace', action='store_true')
    commands.add_parser('credential-put').add_argument('router_id')
    args = parser.parse_args()
    try:
        if not re.fullmatch(ROUTER_ID, args.router_id):
            raise ValueError('OBSERVATION_ROUTER_ID_REJECTED')
        if args.command == 'credential-put':
            if os.geteuid() != pwd.getpwnam(USER).pw_uid or os.geteuid() == 0 or not sys.stdin.isatty():
                raise ValueError('OBSERVATION_VAULT_USER_REQUIRED')
            username = input('Salt okunur RouterOS kullanıcı adı: ')
            password = getpass('RouterOS parolası: ')
            print(observer_vault(args.router_id).put(username, password))
            return
        if args.command == 'export-registry':
            export_registry(args.router_id)
            return
        if os.geteuid() != 0:
            raise ValueError('OBSERVATION_ROOT_REQUIRED')
        directory = open_grants()
        try:
            fcntl.flock(directory, fcntl.LOCK_EX)
            if args.command == 'approve':
                raw = sys.stdin.buffer.read(MAX_GRANT_BYTES + 1)
                if len(raw) > MAX_GRANT_BYTES:
                    raise ValueError('OBSERVATION_INPUT_SIZE_REJECTED')
                approve(directory, args.router_id, json.loads(raw), args.replace)
            else:
                revoke(directory, args.router_id)
        finally:
            os.close(directory)
        print('OBSERVATION_GRANT_APPROVED' if args.command == 'approve' else 'OBSERVATION_GRANT_REVOKED')
    except (ApiSslStop, OSError, ValueError, KeyError, TypeError):
        parser.exit(1, 'OBSERVATION_ACCESS_OPERATION_REJECTED\n')


if __name__ == '__main__':
    main()
