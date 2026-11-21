"""Persistent authorization for standalone observers. The API only reads these grants."""
from dataclasses import dataclass
import grp
import os
from pathlib import Path
import re
import stat
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.cebeci_api_ssl import ApiSslStop
from app.adapters.router_api_ssl import ConnectionPolicy, Target
from app.schemas.device_inventory import Projection, Text

GRANTS = Path('/etc/mikrotik-v2-observers')
RUN = Path('/run')
PREFIX = 'mikrotik-v2-observer-'
USER = 'mtv2-router-observer'
GROUP = 'mtv2-cebeci-read'
MAX_ROUTERS = 16
MAX_GRANT_BYTES = 512 * 1024
ROUTER_ID = r'registered-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'


@dataclass(frozen=True)
class Scope:
    address: str
    source: str
    port: int

    def policy(self):
        policy = ConnectionPolicy(True, self.source, (self.address + '/32',), (self.port,))
        policy.validate(self.address, self.port)
        return policy


class Grant(Projection):
    scope: Literal['ROUTEROS_READ_ONLY']
    router_id: str = Field(pattern='^' + ROUTER_ID + '$')
    grant_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    name: Text
    management_address: str = Field(max_length=15)
    source_ip: str = Field(max_length=15)
    port: int = Field(ge=1024, le=65535, strict=True)
    configuration_revision: int = Field(ge=1, strict=True)
    leaf_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    identity: Text
    model: Text
    routeros_version: str = Field(min_length=3, max_length=64)
    credential_ref: UUID
    read_only_username: str = Field(pattern=r'^[A-Za-z0-9_.-]{1,128}$')
    wan_interface: Text | None = None


class RouterTrust(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    ca_pem: str = Field(min_length=1, max_length=262144)


class GrantDocument(Projection):
    grant: Grant
    trust: RouterTrust

    def target(self):
        item = self.grant
        return Target(item.management_address, item.port, self.trust.ca_pem,
                      item.leaf_sha256, item.identity, item.routeros_version, item.model)


def open_grants(root=GRANTS):
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o755:
        os.close(fd)
        raise ValueError('OBSERVATION_GRANT_DIRECTORY_REJECTED')
    return fd


def read_document(router_id, *, directory=None):
    if not re.fullmatch(ROUTER_ID, router_id):
        raise ValueError('OBSERVATION_ROUTER_ID_REJECTED')
    if directory is None:
        fd = open_grants()
        try:
            return read_document(router_id, directory=fd)
        finally:
            os.close(fd)
    try:
        group = grp.getgrnam(GROUP).gr_gid
    except KeyError:
        raise ValueError('OBSERVATION_GRANT_GROUP_MISSING') from None
    fd = os.open(router_id + '.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or info.st_gid != group or stat.S_IMODE(info.st_mode) != 0o640 or info.st_size > MAX_GRANT_BYTES):
            raise ValueError('OBSERVATION_GRANT_FILE_REJECTED')
        raw = stream.read(MAX_GRANT_BYTES + 1)
    if len(raw) > MAX_GRANT_BYTES:
        raise ValueError('OBSERVATION_GRANT_SIZE_REJECTED')
    document = GrantDocument.model_validate_json(raw)
    grant = document.grant
    if grant.router_id != router_id:
        raise ValueError('OBSERVATION_GRANT_SCOPE_REJECTED')
    Scope(grant.management_address, grant.source_ip, grant.port).policy()
    return document


def documents():
    try:
        directory = open_grants()
    except FileNotFoundError:
        return []
    try:
        ids = []
        with os.scandir(directory) as entries:
            for entry in entries:
                if re.fullmatch(ROUTER_ID + r'\.json', entry.name):
                    ids.append(entry.name.removesuffix('.json'))
                    if len(ids) > MAX_ROUTERS:
                        raise ValueError('OBSERVATION_ROUTER_CAPACITY')
        result = []
        for router_id in sorted(ids):
            try:
                result.append(read_document(router_id, directory=directory))
            except (OSError, ValueError, ApiSslStop):
                # A single invalid, revoked, or unreadable grant cannot hide other routers.
                continue
        return result
    finally:
        os.close(directory)


def approval(document):
    """Require the exact current grant, including its generation and trust material."""
    try:
        if read_document(document.grant.router_id) == document:
            return document.grant.grant_id
    except (OSError, ValueError, ApiSslStop):
        pass
    raise ApiSslStop('OBSERVATION_GRANT_REVOKED')


def registry_material(row):
    """Export the already verified registry endpoint and trust without vault contents."""
    pending = row.configuration.get('onboarding_state') == 'PENDING_VERIFICATION'
    material = dict(router_id=row.id, name=row.name, management_address=row.management_address,
                    port=row.port, configuration_revision=row.revision, pending_verification=pending)
    if pending:
        return material
    if not row.last_success_at:
        raise ValueError('OBSERVATION_ROUTER_NOT_VERIFIED')
    config = row.configuration
    metadata = row.metadata_snapshot
    return dict(material, source_ip=config['source_ip'], leaf_sha256=config['leaf_sha256'],
                identity=config.get('expected_identity') or metadata['identity'],
                model=config.get('expected_model') or metadata['model'],
                routeros_version=config.get('expected_version') or metadata['routeros_version'],
                trust={'ca_pem': config['ca_pem']})
