"""Pure VDS profile guards. No deployment, credentials, DB query or network access."""
import os
from pathlib import Path
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

VDS_PROFILE = 'cebeci-vds'
VDS_ROOT = Path('/srv/mikrotik-manager-v2-pilot')
# User-verified OFFICE identity. This does not create/transfer an account on the VDS.
VDS_OPERATOR_ID = 'v2-user-b72c04eb-8000-4f2c-a41a-bc4909cddb92'


def validate_scope(environment=None):
    values = os.environ if environment is None else environment
    if 'V2_DEPLOYMENT_PROFILE' not in values:
        return
    if values['V2_DEPLOYMENT_PROFILE'] != VDS_PROFILE:
        raise RuntimeError('V2_PILOT_PROFILE_REJECTED')
    from app.adapters.cebeci_api_ssl import REVIEWED_LEAF_SHA256
    expected = {
        'V2_ROUTER_ONBOARDING_SOURCE_IP': '10.250.0.1',
        'V2_ROUTER_ONBOARDING_ALLOWED_CIDRS': '10.250.0.19/32',
        'V2_ROUTER_ONBOARDING_ALLOWED_PORTS': '8729',
        'V2_ROUTER_ONBOARDING_OPERATOR_IDS': VDS_OPERATOR_ID,
        'V2_CEBECI_API_SSL_HOST': '10.250.0.19',
        'V2_CEBECI_API_SSL_PORT': '8729',
        'V2_CEBECI_API_SSL_SOURCE_IP': '10.250.0.1',
        'V2_CEBECI_API_SSL_LEAF_SHA256': REVIEWED_LEAF_SHA256,
    }
    if any(values.get(key) != value for key, value in expected.items()):
        raise RuntimeError('V2_PILOT_SCOPE_REJECTED')
    flags = [values.get(key) for key in ('V2_ROUTER_ONBOARDING_ENABLED', 'V2_CEBECI_API_SSL_ENABLED')]
    if flags[0] not in ('false', 'true') or flags[1] != flags[0]:
        raise RuntimeError('V2_PILOT_GATE_CONFIGURATION_REJECTED')


def operator_in_profile(user_id):
    if 'V2_DEPLOYMENT_PROFILE' not in os.environ:
        return True  # Existing non-VDS onboarding retains its own configured allowlist.
    return os.environ['V2_DEPLOYMENT_PROFILE'] == VDS_PROFILE and user_id == VDS_OPERATOR_ID


def validate_target(target, username):
    if 'V2_DEPLOYMENT_PROFILE' not in os.environ:
        return
    validate_scope()
    from app.adapters.cebeci_api_ssl import REVIEWED_LEAF_SHA256
    if os.environ['V2_ROUTER_ONBOARDING_ENABLED'] != 'true' or (
        target.address, target.port, target.expected_identity, target.expected_model,
        target.expected_version, target.leaf_sha256, username
    ) != ('10.250.0.19', 8729, 'CEBECI_TOWERS', 'RB3011UiAS', '6.49.19', REVIEWED_LEAF_SHA256, 'v2-cebeci-ro'):
        raise RuntimeError('V2_PILOT_TARGET_REJECTED')


def validate_runtime(root, environment=None):
    values = os.environ if environment is None else environment
    validate_scope(values)
    if 'V2_DEPLOYMENT_PROFILE' not in values:
        return
    expected = {
        'V2_API_PORT': '18080',
        'V2_CEBECI_API_SSL_CA_FILE': str(VDS_ROOT / 'app/.local/cebeci-pilot/trust/ca.pem'),
        'V2_CEBECI_API_SSL_USERNAME_FILE': str(VDS_ROOT / 'app/.local/cebeci-pilot/secrets/username'),
        'V2_CEBECI_API_SSL_PASSWORD_FILE': str(VDS_ROOT / 'app/.local/cebeci-pilot/secrets/password'),
    }
    if Path(root) != VDS_ROOT / 'app' or any(values.get(key) != value for key, value in expected.items()):
        raise RuntimeError('V2_PILOT_RUNTIME_PATH_REJECTED')
    try:
        url = make_url(values.get('V2_DATABASE_URL', ''))
        valid = (url.drivername == 'postgresql+psycopg' and url.host == '127.0.0.1'
                 and url.port == 55432 and url.database == 'mikrotik_manager_v2' and url.username == 'v2_local'
                 and not url.query and url.password is not None and len(url.password) >= 20
                 and not any(ord(c) < 32 for c in url.password)
                 and 'REPLACE_' not in url.password and 'PLACEHOLDER' not in url.password)
    except (ArgumentError, ValueError, TypeError):
        valid = False
    if not valid:
        # Never include a DSN, password or parser exception in the diagnostic.
        raise RuntimeError('V2_PILOT_DATABASE_CONFIGURATION_REJECTED') from None
