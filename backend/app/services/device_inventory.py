"""Consume a bounded, dedicated V2 poller export without connecting to devices."""
import grp
import os
import pwd
import stat
from datetime import datetime, timedelta, timezone
from app.schemas.device_inventory import DeviceInventory, RouterObservation
from app.adapters.cebeci_api_ssl import ApiSslStop
from app.services.device_poller import MANAGED_DIR, MANAGED_GROUP, MANAGED_USER, OBSERVATION_NAME

MAX_BYTES = 4 * 1024 * 1024
FRESH_SECONDS = 300

def _read_snapshot(path, *, directory=None, owner=None, group=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES or info.st_nlink != 1:
            raise ValueError()
        mode = stat.S_IMODE(info.st_mode)
        if directory is None:
            if info.st_uid not in (0, os.geteuid()) or mode & 0o077:
                raise ValueError()
        elif (info.st_uid, info.st_gid, mode) != (owner, group, 0o640):
            raise ValueError()
        raw = stream.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise ValueError()
    return DeviceInventory.model_validate_json(raw)


def _managed_snapshot(path=None, username=MANAGED_USER):
    path = MANAGED_DIR if path is None else path
    try:
        owner = pwd.getpwnam(username).pw_uid
        group = grp.getgrnam(MANAGED_GROUP).gr_gid
    except KeyError:
        raise ValueError() from None
    if owner in (0, os.geteuid()) or group == 0:
        raise ValueError()
    try:
        directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(directory)
            if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (owner, group, 0o750):
                raise ValueError()
            return _read_snapshot(OBSERVATION_NAME, directory=directory, owner=owner, group=group)
        finally:
            os.close(directory)
    except FileNotFoundError:
        return None


def read_inventory():
    path = os.environ.get('V2_DEVICE_INVENTORY_FILE')
    mode = os.environ.get('V2_DEVICE_INVENTORY_MODE')
    result = dict(source='ROUTEROS_READ_ONLY', is_demo=False, read_only=True, routers=[])
    if mode == 'multi-router-systemd' and not path:
        return _multi_inventory(result)
    if mode == 'cebeci-systemd' and not path:
        data = _managed_snapshot()
    elif not mode and path and os.path.isabs(path):
        data = _read_snapshot(path)
    elif not mode and not path:
        return result
    else:
        raise ValueError()
    if data is None:
        return result
    if data.grant_id is not None:
        raise ValueError()
    now = datetime.now(timezone.utc)
    if mode:
        item = _pilot_row(data, now)
        if item is not None:
            result['authorization_expires_at'] = data.authorized_until.isoformat()
            result['routers'].append(item)
        return result
    if data.authorized_until is not None:
        raise ValueError()
    if len({row.id for row in data.routers}) != len(data.routers):
        raise ValueError()
    result['routers'] = [_project(row, now) for row in data.routers]
    return result


def _pilot_row(data, now):
    from app.adapters.cebeci_observer import IDENTITY, MODEL, ROUTER_ID, VERSION

    expiry = data.authorized_until
    if data.grant_id is not None or expiry is None or expiry.utcoffset() != timedelta(0) or expiry > now + timedelta(hours=24):
        raise ValueError()
    if expiry <= now:
        return None
    if len(data.routers) != 1:
        raise ValueError()
    row = data.routers[0]
    if (row.id != ROUTER_ID or row.observed_at >= expiry
            or row.connection == 'ONLINE' and (row.identity, row.model, (row.routeros_version or '').removesuffix(' (stable)')) != (IDENTITY, MODEL, VERSION)
            or row.wan_status != 'UNKNOWN' or any(value is not None for value in (row.wan_interface, row.rx_bytes, row.tx_bytes))):
        raise ValueError()
    return _project(row, now)


def _project(row, now):
    if (row.observed_at > now or row.last_success_at and row.last_success_at > row.observed_at
        or row.connection == 'ONLINE' and (row.last_success_at != row.observed_at or row.error)
        or row.connection == 'OFFLINE' and row.error != 'UNREACHABLE'
        or row.accounts and len({account.username for account in row.accounts}) != len(row.accounts)):
        raise ValueError()
    fresh = (now-row.observed_at).total_seconds() < FRESH_SECONDS
    current = fresh and row.connection == 'ONLINE'
    item = row.model_dump(mode='json')
    item['freshness'] = 'RECENT' if fresh else 'STALE'
    if not fresh:
        item['connection'] = 'UNKNOWN'
    if not current:
        for key in ('cpu_percent','memory_percent','uptime','wan_interface','rx_bytes','tx_bytes','accounts','unmatched_sessions'):
            item[key] = None
        item.update(wan_status='UNKNOWN',accounts_complete=False)
    for key in ('rx_bytes','tx_bytes'):
        if item[key] is not None:
            item[key] = str(item[key])
    return item


def _multi_inventory(result):
    from app.adapters.cebeci_observer import ADDRESS, PORT
    from app.services.router_observation_grants import PREFIX, RUN, USER, approval, documents

    now = datetime.now(timezone.utc)
    documents_by_router = documents()
    legacy_replaced = False
    for document in documents_by_router:
        grant = document.grant
        router_id = 'device-' + grant.router_id
        item = dict(id=router_id, identity=grant.identity, model=grant.model,
                    routeros_version=grant.routeros_version, freshness='STALE',
                    connection='UNKNOWN', observed_at=None, last_success_at=None,
                    accounts=None, accounts_complete=False, unmatched_sessions=None,
                    error=None, cpu_percent=None, memory_percent=None, uptime=None, wan_interface=None,
                    wan_status='UNKNOWN', rx_bytes=None, tx_bytes=None)
        try:
            data = _managed_snapshot(RUN / (PREFIX + grant.router_id), USER)
            if data and data.grant_id == grant.grant_id and data.authorized_until is None and len(data.routers) == 1:
                row = data.routers[0]
                if (row.id == router_id and (row.connection != 'ONLINE' or
                    (row.identity, row.model, (row.routeros_version or '').removesuffix(' (stable)')) ==
                    (grant.identity, grant.model, grant.routeros_version.removesuffix(' (stable)')))):
                    item = _project(row, now)
        except (OSError, ValueError):
            pass
        item.update(name=grant.name, identity=item.get('identity') or grant.identity,
                    management_address=grant.management_address, port=grant.port,
                    access='PERSISTENT', wan_interface_configured=grant.wan_interface)
        try:
            approval(document)
        except ApiSslStop:
            continue
        result['routers'].append(item)
        legacy_replaced |= (grant.management_address, grant.port) == (ADDRESS, PORT)
    if not legacy_replaced:
        try:
            data = _managed_snapshot()
            legacy = _pilot_row(data, now) if data else None
            if legacy is not None:
                legacy.update(access='PILOT', authorization_expires_at=data.authorized_until.isoformat())
                result['routers'].append(legacy)
        except (OSError, ValueError):
            pass
    return result


def sample_device(client, target, credentials, policy, *, router_id, wan_interface, previous=None):
    """One poll cycle for an authorized external worker. Never called by the API."""
    try:
        return client.read_inventory_observation(target, credentials, policy, router_id=router_id,
                                                 wan_interface=wan_interface)
    except ApiSslStop as failure:
        code = str(failure)
        error = ('UNREACHABLE' if code == 'CONNECTION_UNREACHABLE' else
                 'TIMEOUT' if code.partition(':')[0] in ('CONNECTION_TIMEOUT', 'DEADLINE_EXCEEDED') else
                 'CAPACITY' if code.partition(':')[0] in ('ROW_LIMIT', 'RESPONSE_BYTE_LIMIT', 'SENTENCE_LIMIT') else
                 'TLS' if code.startswith(('TLS_', 'CERTIFICATE_', 'CA_CERTIFICATE_')) else
                 'AUTHORIZATION' if code.startswith(('AUTHENTICATION', 'DEDICATED_', 'CREDENTIAL_', 'PILOT_', 'POLL_TARGET_', 'ONBOARDING_', 'TARGET_OR_SOURCE_')) else
                 'INVALID_DATA')
        previous = previous if previous and previous.id == router_id and previous.identity == target.expected_identity else None
        return RouterObservation(id=router_id, observed_at=datetime.now(timezone.utc),
            connection='OFFLINE' if error == 'UNREACHABLE' else 'UNKNOWN', error=error,
            identity=previous.identity if previous else None, model=previous.model if previous else None,
            routeros_version=previous.routeros_version if previous else None,
            last_success_at=previous.last_success_at if previous else None)
