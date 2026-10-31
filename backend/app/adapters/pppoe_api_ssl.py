"""Opt-in RouterOS API-SSL PPPoE reader. Never registered at startup.

RouterOS >=6.43 and 7 use the same login/print protocol. Older challenge
login is deliberately rejected; TLS and authentication are never downgraded.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from ipaddress import IPv4Address
import hashlib
import hmac
import math
import re
import socket
import ssl
import time
from app.adapters.cebeci_api_ssl import ApiSslStop, _Wire
from app.adapters.router_api_ssl import ConnectionPolicy
from app.adapters.pppoe_readonly import RouterReadSettings
from app.integrations.cebeci_access import verified_tls_context


_QUERY = ('/ppp/active/print', '=.proplist=name,service,address,radius')


class _PppoeWire(_Wire):
    def send(self, words):
        # Enforce the allowlist at the actual emission boundary, including auth.
        login = (len(words) == 3 and words[0] == '/login'
                 and words[1].startswith('=name=') and words[2].startswith('=password='))
        if tuple(words) != _QUERY and not login:
            raise ApiSslStop('READ_SCOPE_REJECTED')
        super().send(words)

    def active(self):
        self.send(_QUERY)
        rows = []
        while True:
            words = self.sentence()
            if words == ['!done']:
                return rows
            if words == ['!empty']:  # RouterOS 7.18+ still terminates with !done.
                if rows:
                    raise ValueError('INVALID_DATA')
                continue
            if not words or words[0] != '!re':
                raise ApiSslStop('READ_FAILED')
            row = {}
            for word in words[1:]:
                parts = word.split('=', 2)
                if len(parts) != 3 or parts[0] or parts[1] not in ('name', 'service', 'address', 'radius') or parts[1] in row:
                    raise ValueError('INVALID_DATA')
                if not parts[2] or any(ord(c) < 32 for c in parts[2]):
                    raise ValueError('INVALID_DATA')
                row[parts[1]] = parts[2]
            if set(row) != {'name', 'service', 'address', 'radius'} or row['radius'] not in ('true', 'false', 'yes', 'no'):
                raise ValueError('INVALID_DATA')
            rows.append(row)
            if len(rows) > 128:
                raise ValueError('INVALID_DATA')


@dataclass(frozen=True)
class PppoeAccount:
    account_id: str
    username: str = field(repr=False)
    source: str


class RouterPppoeApiSslTransport:
    """One router per instance; inventory is explicit, never discovered by name.

    Both policy.enabled and the application's explicit router binding are
    required. No environment flag installs this transport or grants permission.
    """
    def __init__(self, settings: RouterReadSettings, accounts: tuple[PppoeAccount, ...],
                 policy: ConnectionPolicy = ConnectionPolicy()):
        self._settings = settings
        self._accounts = tuple(accounts)
        self._policy = policy

    def read_pppoe(self, settings: RouterReadSettings) -> list[dict]:
        if settings != self._settings:
            raise ValueError('INVALID_DATA')
        accounts = self._accounts
        if (not accounts or len(accounts) > 128
                or len({a.account_id for a in accounts}) != len(accounts)
                or len({a.username for a in accounts}) != len(accounts)
                or any(not a.account_id or not a.username or a.source not in ('LOCAL', 'RADIUS') for a in accounts)):
            raise ValueError('INVALID_DATA')
        self._policy.validate(settings.address, settings.port)
        if (str(IPv4Address(settings.address)) != settings.address or settings.port != 8729
                or not math.isfinite(settings.timeout_seconds) or not .1 <= settings.timeout_seconds <= 10
                or not re.fullmatch('[a-f0-9]{64}', settings.leaf_sha256)):
            raise ValueError('INVALID_DATA')
        context = verified_tls_context(settings.ca_pem)
        if (context.verify_mode != ssl.CERT_REQUIRED or context.check_hostname is not True
                or context.minimum_version < ssl.TLSVersion.TLSv1_2
                or context.hostname_checks_common_name is not False):
            raise ApiSslStop('TLS_POLICY_REJECTED')
        deadline = time.monotonic() + settings.timeout_seconds
        raw = secure = None
        try:
            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            def budget(stream):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                stream.settimeout(remaining)
            budget(raw)
            raw.bind((self._policy.source_ip, 0))
            raw.connect((settings.address, settings.port))
            budget(raw)
            secure = context.wrap_socket(raw, server_hostname=settings.address)
            budget(secure)
            if (secure.getpeername()[:2] != (settings.address, settings.port)
                    or secure.getsockname()[0] != self._policy.source_ip
                    or secure.version() not in ('TLSv1.2', 'TLSv1.3')):
                raise ApiSslStop('TLS_ENDPOINT_REJECTED')
            cert = secure.getpeercert(binary_form=True)
            if (not cert or not hmac.compare_digest(hashlib.sha256(cert).hexdigest(), settings.leaf_sha256)
                    or ('IP Address', settings.address) not in secure.getpeercert().get('subjectAltName', ())):
                raise ApiSslStop('TLS_CERTIFICATE_REJECTED')
            wire = _PppoeWire(secure, deadline, settings.timeout_seconds)
            wire.login(credentials=(settings.username, settings.password.get_secret_value()))
            rows = wire.active()
            wire.timeout()
            by_name = {a.username: a for a in accounts}
            result = []
            seen = set()
            observed = datetime.now(timezone.utc)
            for row in rows:
                if settings.password.get_secret_value() in str(row):
                    raise ValueError('INVALID_DATA')
                if row['service'] != 'pppoe' or row['name'] not in by_name:
                    continue
                account = by_name[row['name']]
                source = 'RADIUS' if row['radius'] in ('true', 'yes') else 'LOCAL'
                if source != account.source or account.account_id in seen:
                    raise ValueError('INVALID_DATA')
                seen.add(account.account_id)
                address = str(IPv4Address(row['address']))
                result.append(dict(account_id=account.account_id, source=source,
                                   connected=True, ip_address=address, observed_at=observed))
            budget(secure)
            return result
        except ApiSslStop as error:
            if str(error) == 'DEADLINE_EXCEEDED':
                raise TimeoutError() from None
            raise ApiSslStop('PPPOE_CONNECTION_FAILED') from None
        finally:
            for stream in (secure, raw):
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
