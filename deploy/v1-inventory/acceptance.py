"""Shared, transport-injected inventory acceptance. Never prints API bodies or secrets."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import urllib.error

from static_acceptance import verify_scripts, StaticAcceptanceError


def summary(value):
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        if value in {'V1_INVENTORY_EXPORT', 'V1_ROUTER_HEALTH_SAMPLES', 'NO_DATA',
                     'STALE', 'RECENT', 'LAST_PROBE_SUCCEEDED', 'LAST_PROBE_FAILED'}:
            return value
        return {'type': 'str', 'sha256': sha256(value.encode()).hexdigest()}
    if isinstance(value, (list, dict)):
        return {'type': type(value).__name__, 'count': len(value)}
    return {'type': type(value).__name__}


class AcceptanceError(ValueError):
    def __init__(self, step, expected, actual, api_error=None):
        self.report = dict(status='BLOCKED', step=step, expected=expected, actual=actual)
        if api_error is not None:
            self.report['api_error'] = api_error
        super().__init__(json.dumps(self.report, sort_keys=True))


def equal(step, expected, actual):
    if expected != actual or (type(expected) is bool and type(actual) is not bool):
        raise AcceptanceError(step, summary(expected), summary(actual))


def verify_inventory(result, snapshot, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(result, dict):
        raise AcceptanceError('api.shape', 'object', summary(result))
    equal('api.source', 'V1_INVENTORY_EXPORT', result.get('source'))
    equal('api.is_demo', False, result.get('is_demo'))
    rows = result.get('items')
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise AcceptanceError('api.items.shape', 'list of objects', summary(rows))
    expected = {r['id']: r for r in snapshot['items']}
    ids = [r.get('id') for r in rows]
    if not all(isinstance(i, str) for i in ids) or len(set(ids)) != len(ids) or set(ids) != set(expected):
        raise AcceptanceError('api.identity_set', {'count': len(expected), 'unique_matching_ids': True},
                              {'count': len(rows), 'unique_matching_ids': False})
    health = {s['router_id']: s for s in snapshot.get('health_samples', [])}
    if len(health) != len(snapshot.get('health_samples', [])) or not set(health) <= set(expected):
        raise AcceptanceError('snapshot.health_identity', 'unique matched IDs', 'invalid')
    missing = dict.fromkeys(('cpu_load_percent', 'memory_used_percent', 'sampled_at', 'health_source', 'internet_success'), 0)
    visible = stale = 0
    for index, row in enumerate(rows):
        prefix = f'api.items[{index}]'
        required = {'id', 'name', 'identity', 'model', 'routeros_version', 'status',
                    'sampled_at', 'freshness', 'cpu_load_percent', 'memory_used_percent',
                    'health_source', 'health_sample_id', 'connection_status'}
        if not required <= row.keys():
            raise AcceptanceError(prefix+'.fields', sorted(required),
                                  {'missing_fields': sorted(required-row.keys())})
        meta = expected[row['id']]
        for field in ('id', 'name', 'identity', 'model', 'routeros_version'):
            equal(prefix+'.'+field, meta.get(field), row.get(field))
        equal(prefix+'.status', 'NO_DATA', row.get('status'))
        sample = health.get(row['id'])
        source = sample or meta
        stamp = source.get('sampled_at')
        if stamp:
            try:
                measured = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
                actual = datetime.fromisoformat(row['sampled_at'].replace('Z', '+00:00'))
                age = (now-measured).total_seconds()
                if measured.tzinfo is None or age < 0:
                    raise ValueError()
            except (TypeError, ValueError, KeyError, AttributeError):
                raise AcceptanceError(prefix+'.sampled_at', 'valid nonfuture aware timestamp', summary(row.get('sampled_at'))) from None
            equal(prefix+'.sampled_at', measured, actual)
            freshness = 'STALE' if age > 300 else 'RECENT'
            stale += age > 300
        else:
            equal(prefix+'.sampled_at', None, row.get('sampled_at'))
            freshness = 'NO_DATA'
        equal(prefix+'.freshness', freshness, row.get('freshness'))
        for field in ('cpu_load_percent', 'memory_used_percent'):
            equal(prefix+'.'+field, source.get(field) if stamp else None, row.get(field))
        equal(prefix+'.health_source', 'V1_ROUTER_HEALTH_SAMPLES' if sample else None, row.get('health_source'))
        equal(prefix+'.health_sample_id', sample['id'] if sample else None, row.get('health_sample_id'))
        probe = sample.get('internet_success') if sample else None
        equal(prefix+'.connection_status', 'NO_DATA' if probe is None else 'LAST_PROBE_SUCCEEDED' if probe else 'LAST_PROBE_FAILED', row.get('connection_status'))
        visible += sample is not None
        for field in missing:
            missing[field] += (probe is None) if field == 'internet_success' else row.get(field) is None
    return dict(router_count=len(rows), health_visible=visible, stale=stale, missing=missing)


def accept_authenticated(client, url, snapshot, files, now=None):
    """Use an already authenticated client; login/logout remain caller-owned."""
    def read(step, path):
        try:
            with client.open(url+path, timeout=5) as response:
                body = response.read(1024*1024+1)
                if len(body) > 1024*1024:
                    raise AcceptanceError(step, 'bounded response', 'oversized')
                return body
        except urllib.error.HTTPError as error:
            raise AcceptanceError(step, 200, error.code,
                                  {'kind': 'HTTPError', 'status': error.code}) from None
        except (OSError, urllib.error.URLError):
            raise AcceptanceError(step, 'HTTP response', 'transport failure',
                                  {'kind': 'transport'}) from None
    raw = read('api.inventory.http', '/api/v1/v1-inventory')
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise AcceptanceError('api.inventory.json', 'JSON object', 'invalid JSON',
                              {'kind': 'invalid_json'}) from None
    receipt = verify_inventory(result, snapshot, now)
    try:
        html = read('ui.index.http', '/').decode('utf-8')
    except UnicodeError:
        raise AcceptanceError('ui.index.encoding', 'UTF-8', 'invalid encoding') from None
    try:
        hashes = verify_scripts(html, lambda path: read('ui.script.http', path), files)
    except StaticAcceptanceError as error:
        # The helper emits only fixed codes and SHA256 digests, never script text.
        raise AcceptanceError('ui.script.sha256', 'approved script bytes', str(error)) from None
    return dict(status='PASS', **receipt, script_sha256=hashes)
