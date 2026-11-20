"""Consume a bounded, dedicated V2 poller export without connecting to devices."""
import os
import stat
from datetime import datetime, timezone
from app.schemas.device_inventory import DeviceInventory, RouterObservation
from app.adapters.cebeci_api_ssl import ApiSslStop

MAX_BYTES = 4 * 1024 * 1024
FRESH_SECONDS = 300

def read_inventory():
    path = os.environ.get('V2_DEVICE_INVENTORY_FILE')
    result = dict(source='ROUTEROS_READ_ONLY', is_demo=False, read_only=True, routers=[])
    if not path:
        return result
    if not os.path.isabs(path):
        raise ValueError()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES or info.st_nlink != 1 or info.st_uid not in (0, os.geteuid()) or info.st_mode & 0o077:
            raise ValueError()
        raw = stream.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise ValueError()
    data = DeviceInventory.model_validate_json(raw)
    now = datetime.now(timezone.utc)
    if len({row.id for row in data.routers}) != len(data.routers):
        raise ValueError()
    for row in data.routers:
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
        result['routers'].append(item)
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
                 'TLS' if code.startswith(('TLS_', 'CERTIFICATE_', 'CA_CERTIFICATE_')) else
                 'AUTHORIZATION' if code.startswith(('AUTHENTICATION', 'DEDICATED_', 'CREDENTIAL_', 'PILOT_', 'POLL_TARGET_', 'ONBOARDING_', 'TARGET_OR_SOURCE_')) else
                 'INVALID_DATA')
        previous = previous if previous and previous.id == router_id and previous.identity == target.expected_identity else None
        return RouterObservation(id=router_id, observed_at=datetime.now(timezone.utc),
            connection='OFFLINE' if error == 'UNREACHABLE' else 'UNKNOWN', error=error,
            identity=previous.identity if previous else None, model=previous.model if previous else None,
            routeros_version=previous.routeros_version if previous else None,
            last_success_at=previous.last_success_at if previous else None)
