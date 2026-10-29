"""Explicit bridge to the existing private V2 pilot material; never scans V1 or logs values."""
from app.adapters.cebeci_api_ssl import _read_pilot_file,PILOT_RUNTIME_ROOT,REVIEWED_LEAF_SHA256,ApiSslStop
from app.schemas.router_registry import RouterCandidate

ALIAS='CEBECI_TOWERS_RO'

def candidate(payload,policy):
    policy.validate('10.250.0.19',8729)
    if policy.source_ip!='10.250.0.1':raise ApiSslStop('PILOT_SCOPE_MISMATCH')
    name=_read_pilot_file(str(PILOT_RUNTIME_ROOT/'secrets/username'),128)
    if name!='v2-cebeci-ro':raise ApiSslStop('PILOT_ACCOUNT_MISMATCH')
    password=_read_pilot_file(str(PILOT_RUNTIME_ROOT/'secrets/password'),1024)
    ca=_read_pilot_file(str(PILOT_RUNTIME_ROOT/'trust/ca.pem'),262144)
    return RouterCandidate(request_id=payload.request_id,name=payload.name,management_address='10.250.0.19',port=8729,
        username=name,password=password,ca_pem=ca,leaf_sha256=REVIEWED_LEAF_SHA256,
        expected_identity='CEBECI_TOWERS',expected_version='6.49.19',expected_model='RB3011UiAS',confirmed_read_only=True)
