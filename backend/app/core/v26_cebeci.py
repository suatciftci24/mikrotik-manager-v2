"""Explicit CEBECI read capability inside the unchanged V2.6 acceptance identity.

No IO, implicit operator, generic onboarding grant or startup connection.
"""
import os
import re

FLAG = 'V2_V26_CEBECI_READ_ENABLED'
OPERATOR = 'V2_V26_CEBECI_OPERATOR_ID'
REVISION = 'V2_V26_CEBECI_OPERATOR_REVISION'


def validate(values):
    flag = values.get(FLAG, 'false')
    identity = values.get(OPERATOR, '')
    revision = values.get(REVISION, '')
    valid = flag in ('false', 'true')
    if flag == 'true':
        valid = (valid and values.get('V2_DEPLOYMENT_PROFILE') == 'v26-isolated-acceptance'
                 and isinstance(identity, str)
                 and re.fullmatch(r'v2-user-[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', identity)
                 and isinstance(revision, str) and re.fullmatch(r'0|[1-9][0-9]{0,9}', revision))
    else:
        valid = valid and identity == '' and revision == ''
    if not valid:
        raise RuntimeError('V26_CEBECI_CAPABILITY_REJECTED')


def in_profile(values=None):
    values = os.environ if values is None else values
    return values.get('V2_DEPLOYMENT_PROFILE') == 'v26-isolated-acceptance'


def enabled(values=None):
    values = os.environ if values is None else values
    validate(values)
    return in_profile(values) and values.get(FLAG, 'false') == 'true'


def operator_allowed(user):
    from app.core.pilot_operator import pilot_identity
    from app.core import v26_acceptance
    try:
        v26_acceptance.validate_current()
        if not enabled():
            return False
        identity = pilot_identity(user)
        return (identity['state'] == 'ELIGIBLE'
                and identity['candidate']['id'] == os.environ[OPERATOR]
                and str(identity['candidate']['revision']) == os.environ[REVISION])
    except RuntimeError:
        return False


def policy():
    from app.core import v26_acceptance
    from app.adapters.router_api_ssl import ConnectionPolicy
    v26_acceptance.validate_current()
    return ConnectionPolicy(enabled(), '10.250.0.1', ('10.250.0.19/32',), (8729,))


def require_scope(address, port, configuration):
    """Never let existing unrelated registry rows/proofs enter the capability."""
    if not in_profile():
        return
    from app.adapters.cebeci_api_ssl import ApiSslStop, REVIEWED_LEAF_SHA256
    expected = dict(pilot_kind='CEBECI_TOWERS', source_ip='10.250.0.1',
                    expected_identity='CEBECI_TOWERS', expected_model='RB3011UiAS',
                    expected_version='6.49.19', leaf_sha256=REVIEWED_LEAF_SHA256)
    if (not enabled() or (address, port) != ('10.250.0.19', 8729)
            or any(configuration.get(k) != v for k, v in expected.items())):
        raise ApiSslStop('PILOT_SCOPE_MISMATCH')
