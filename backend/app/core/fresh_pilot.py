"""Closed, independent fresh pilot identity. Pure checks; never opens connections."""
from pathlib import Path
import os

PROFILE = 'fresh-v2-pilot'
ROOT = Path('/srv/mikrotik-manager-v2-fresh-pilot')
DB = 'mikrotik_manager_v2_fresh_pilot'
ROLE = 'v2_fresh_app'
PORT = 55442


def active(values=None):
    return (os.environ if values is None else values).get('V2_DEPLOYMENT_PROFILE') == PROFILE


def validate(values=None, root=None):
    from sqlalchemy.engine import make_url
    values = os.environ if values is None else values
    try:
        url = make_url(values.get('V2_DATABASE_URL', ''))
        valid = (url.drivername == 'postgresql+psycopg' and url.host == '127.0.0.1'
                 and (url.database, url.username, url.port) == (DB, ROLE, PORT)
                 and not url.query and url.password and len(url.password) >= 32)
    except Exception:
        # Parser errors must never leak credentials.
        valid = False
    flags = {'V2_API_PORT':'18090', 'V2_ROUTER_ONBOARDING_ENABLED':'false',
             'V2_CEBECI_API_SSL_ENABLED':'false', 'V2_ROUTER_ONBOARDING_OPERATOR_IDS':''}
    if (not active(values) or not valid or any(values.get(k) != v for k,v in flags.items())
            or (root is not None and Path(root) != ROOT / 'app')):
        raise RuntimeError('FRESH_PILOT_CONFIGURATION_REJECTED')
