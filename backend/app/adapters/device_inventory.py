"""Read-only collection over an already authorized, authenticated RouterOS wire."""
from datetime import date, datetime, timezone
from types import MappingProxyType
import logging
import re

from app.adapters.cebeci_api_ssl import ApiSslStop, _Wire
from app.schemas.device_inventory import Account, RouterObservation, Session, UnmatchedSession

_FIELDS = MappingProxyType({
    '/system/identity': ('name',),
    '/system/resource': ('board-name', 'version', 'cpu-load', 'total-memory', 'free-memory', 'uptime'),
    '/interface': ('name', 'running', 'disabled', 'rx-byte', 'tx-byte'),
    '/ppp/secret': ('name', 'profile', 'service', 'disabled', 'comment'),
    '/ppp/active': ('name', 'service', 'address', 'uptime'),
})
_COMMANDS = MappingProxyType({
    menu: (('/interface/print', '=stats=') if menu == '/interface' else (menu+'/print',))
          + ('=.proplist='+','.join(fields),)
    for menu, fields in _FIELDS.items()
})
_ALLOWED = frozenset(_COMMANDS.values())
_REQUIRED = {
    '/system/identity': ('name',),
    '/system/resource': ('board-name', 'version'),
    '/ppp/secret': ('name',),
    '/ppp/active': ('name',),
}
_LOG = logging.getLogger(__name__)


class DeviceReadWire(_Wire):
    def send(self, words):
        if tuple(words) not in _ALLOWED:
            raise ApiSslStop('READ_SCOPE_REJECTED')
        super().send(words)

    def fixed_read(self, menu):
        fields = _FIELDS.get(menu)
        if fields is None:
            raise ApiSslStop('READ_SCOPE_REJECTED')
        self.send(_COMMANDS[menu])
        command = _COMMANDS[menu][0]
        keys = {field.encode('ascii'): field for field in fields}
        required = _REQUIRED.get(menu, ())
        rows = []
        warned = set()
        empty_reply = False
        while True:
            try:
                words = self._sentence_bytes()
            except ApiSslStop as error:
                raise ApiSslStop(f'{error}:{command}') from None
            if words == [b'!done']:
                return rows
            if words == [b'!empty'] and not rows and not empty_reply:
                empty_reply = True
                continue
            if not words or words[0] != b'!re' or empty_reply:
                raise ApiSslStop(f'DEVICE_READ_REJECTED:{command}')
            if len(rows) >= 128:
                raise ApiSslStop(f'ROW_LIMIT:{command}')
            row = {}
            for word in words[1:]:
                parts = word.split(b'=', 2)
                field = keys.get(parts[1]) if len(parts) == 3 and not parts[0] else None
                if field is None or field in row:
                    raise ApiSslStop(f'UNEXPECTED_RESPONSE_FIELD:{command}')
                # Strict UTF-8 keeps matching one-to-one with the wire bytes.
                # A guessed codec or replacement could give an account a different name.
                try:
                    value = parts[2].decode('utf8')
                except UnicodeDecodeError:
                    if field not in warned:
                        _LOG.warning('INVALID_TEXT:%s:%s', command, field)
                        warned.add(field)
                    if field in required:
                        raise ApiSslStop(f'INVALID_TEXT:{command}:{field}') from None
                    value = None
                if value is not None and len(value) > 512:
                    raise ApiSslStop(f'FIELD_VALUE_LIMIT:{command}:{field}')
                row[field] = value
            for field in required:
                if not row.get(field):
                    raise ApiSslStop(f'MISSING_RESPONSE_FIELD:{command}:{field}')
            rows.append(row)


def _flag(value):
    return {'true': True, 'yes': True, 'false': False, 'no': False}.get(value)


def _number(value):
    return int(value) if value and value.isascii() and value.isdigit() and len(value) <= 20 else None


def _expiry(comment):
    value = (comment or '').strip()
    match = re.fullmatch(
        r'EXPIRE(?:=|:)\s*(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?',
        value, re.IGNORECASE
    )
    try:
        if match:
            if match[2]:
                datetime.strptime(match[2], '%H:%M')
            return date.fromisoformat(match[1])

        match = re.fullmatch(
            r'(\d{1,2})/(\d{1,2})/(\d{4})\s+kapat',
            value, re.IGNORECASE
        )
        if match:
            return date(int(match[3]), int(match[2]), int(match[1]))
    except ValueError:
        pass
    return None


def collect(wire: DeviceReadWire, router_id: str, expected_identity: str, wan_interface: str | None,
            *, expected_model=None, expected_version=None):
    """The caller owns TLS, login and the existing wire deadline. No retries."""
    try:
        identity, = wire.fixed_read('/system/identity')
        resource, = wire.fixed_read('/system/resource')
        version = resource['version']
        if (not expected_identity or identity['name'] != expected_identity
            or not re.fullmatch(r'(?:6\.49\.\d+|7\.\d+(?:\.\d+)?(?:beta\d+|rc\d+)?)(?: \((?:stable|long-term|testing|development)\))?',version)
            or expected_model and resource['board-name'] != expected_model
            or expected_version and version.removesuffix(' (stable)') != expected_version.removesuffix(' (stable)')):
            raise ValueError()
        interfaces = [r for r in wire.fixed_read('/interface') if r.get('name') == wan_interface] if wan_interface else []
        wan = interfaces[0] if wan_interface and len(interfaces) == 1 else {}
        running, disabled = _flag(wan.get('running')), _flag(wan.get('disabled'))
        wan_status = 'DOWN' if disabled is True or running is False else 'UP' if running is True and disabled is False else 'UNKNOWN'
        secrets = wire.fixed_read('/ppp/secret')
        active = wire.fixed_read('/ppp/active')
        sessions = {}
        for row in active:
            if row.get('service') == 'pppoe':
                sessions.setdefault(row['name'], []).append(Session(address=row.get('address') or None, uptime=row.get('uptime') or None))
        known = []
        names = [row['name'] for row in secrets]
        if len(set(names)) != len(names):
            raise ValueError()
        for row in secrets:
            name, service = row['name'], row.get('service')
            if service != 'pppoe' and not (service == 'any' and name in sessions):
                continue
            disabled = _flag(row.get('disabled'))
            known.append(Account(username=name, profile=row.get('profile') or None,
                enabled=None if disabled is None else not disabled, expires_on=_expiry(row.get('comment')),
                sessions=sessions.get(name) or ([] if all(r.get('service') and r.get('name') for r in active) else None)))
        observed_names = {account.username for account in known}
        active_complete = all(r.get('service') and r.get('name') for r in active)
        unmatched = [UnmatchedSession(username=name, **session.model_dump()) for name, items in sessions.items()
                     if name not in observed_names for session in items]
        total, free = _number(resource.get('total-memory')), _number(resource.get('free-memory'))
        stamp = datetime.now(timezone.utc)
        wire.timeout()
        return RouterObservation(id=router_id, identity=identity['name'], model=resource['board-name'],
            routeros_version=resource['version'], observed_at=stamp, last_success_at=stamp, connection='ONLINE',
            cpu_percent=_number(resource.get('cpu-load')), memory_percent=(100*(total-free)/total if total and free is not None and free<=total else None),
            uptime=resource.get('uptime') or None, wan_interface=wan_interface if wan else None, wan_status=wan_status,
            rx_bytes=_number(wan.get('rx-byte')), tx_bytes=_number(wan.get('tx-byte')), accounts=known,
            accounts_complete=all(r.get('service') not in (None,'any') for r in secrets),
            unmatched_sessions=unmatched if active_complete or unmatched else None)
    except (KeyError, ValueError, TypeError):
        raise ApiSslStop('DEVICE_READ_REJECTED') from None
