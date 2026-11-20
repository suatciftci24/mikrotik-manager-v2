"""Private, expiring authorization for the standalone V2.6.14 observer."""
from datetime import datetime, timedelta, timezone
import json
import os

from app.adapters.cebeci_api_ssl import ApiSslStop, PILOT_RUNTIME_ROOT, REVIEWED_LEAF_SHA256, _read_pilot_file
from app.adapters.router_api_ssl import ConnectionPolicy, RouterApiSslClient, Target

ROOT = PILOT_RUNTIME_ROOT / 'v2614-observer'
ROUTER_ID = 'device-cebeci-towers'
ADDRESS = '10.250.0.19'
PORT = 8729
SOURCE = '10.250.0.1'
IDENTITY = 'CEBECI_TOWERS'
MODEL = 'RB3011UiAS'
VERSION = '6.49.19'
USERNAME = 'v2-cebeci-ro'
SCOPE = 'V2614_CEBECI_TOWERS_READ_ONLY'


def _approval(now=None):
    """Fail before credential reads or transport. Never use legacy app grants."""
    from app.core import v26_cebeci

    try:
        v26_cebeci.validate(os.environ)
        if (os.environ.get('V2_DEPLOYMENT_PROFILE') or os.geteuid() == 0 or os.environ.get('V2_ROUTER_ONBOARDING_OPERATOR_IDS')
            or any(os.environ.get(key, 'false') != 'false' for key in (
                'V2_ROUTER_ONBOARDING_ENABLED', 'V2_CEBECI_API_SSL_ENABLED'))):
            raise ValueError()
        raw = _read_pilot_file(str(ROOT / 'approval.json'), 4096)
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) - {'scope','expires_at','wan_interface'} or data.get('scope') != SCOPE:
            raise ValueError()
        expires = datetime.fromisoformat(data['expires_at'])
        now = now or datetime.now(timezone.utc)
        if expires.utcoffset() != timedelta(0) or not now < expires <= now + timedelta(hours=24):
            raise ValueError()
        wan = data.get('wan_interface')
        if wan is not None and (not isinstance(wan, str) or not 1 <= len(wan) <= 120 or not wan.isprintable() or wan != wan.strip()):
            raise ValueError()
        return wan, expires
    except (ApiSslStop, RuntimeError, ValueError, TypeError, KeyError, OverflowError):
        raise ApiSslStop('V2614_CEBECI_OBSERVER_NOT_AUTHORIZED') from None


def authorize(now=None):
    return _approval(now)[0]


def managed_expiry():
    wan, expires = _approval()
    if wan is not None:
        raise ApiSslStop('V2614_CEBECI_OBSERVER_SCOPE_REJECTED')
    return expires


class CebeciObserverClient(RouterApiSslClient):
    def read_inventory_observation(self, target, credentials, policy, *, router_id, wan_interface):
        reviewed_wan = authorize()
        if (target.address, target.port, target.expected_identity, target.expected_model, target.expected_version,
            target.leaf_sha256, credentials[0], policy, router_id, wan_interface) != (
            ADDRESS, PORT, IDENTITY, MODEL, VERSION, REVIEWED_LEAF_SHA256, USERNAME,
            ConnectionPolicy(True, SOURCE, (ADDRESS+'/32',), (PORT,)), ROUTER_ID, reviewed_wan):
            raise ApiSslStop('V2614_CEBECI_OBSERVER_SCOPE_REJECTED')
        policy.validate(target.address, target.port)
        return self._verified_read(target, credentials, policy, False, (router_id, wan_interface))


def make_sampler(*, managed=False):
    """Load dedicated material only after authorization, recheck before every read."""
    check = managed_expiry if managed else authorize
    check()
    ca = _read_pilot_file(str(ROOT / 'ca.pem'), 262144)
    password = _read_pilot_file(str(ROOT / 'password'), 1024)
    if any(char in password for char in '\r\n\x00'):
        raise ApiSslStop('V2614_CEBECI_OBSERVER_CREDENTIAL_REJECTED')

    from app.services.device_inventory import sample_device

    target = Target(ADDRESS, PORT, ca, REVIEWED_LEAF_SHA256, IDENTITY, VERSION, MODEL)
    credentials = (USERNAME, password)
    policy = ConnectionPolicy(True, SOURCE, (ADDRESS+'/32',), (PORT,))
    client = CebeciObserverClient()

    def sample(*, previous):
        approval = check()
        wan = None if managed else approval
        return sample_device(client, target, credentials, policy, router_id=ROUTER_ID,
                             wan_interface=wan, previous=previous)
    return sample
