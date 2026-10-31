"""ADMIN-only central onboarding; reads never connect to devices."""
from app.core.pilot_operator import pilot_identity
import os
from fastapi import APIRouter,Depends,Header,HTTPException,Query,Request
from app.core.security import current_admin
from app.schemas.router_registry import RouterCandidate,RegisterVerified,RecheckRouter,CebeciPilotCandidate,InventoryRouter
from app.services.router_registry import registry,RegistryError
from app.adapters.router_api_ssl import ConnectionPolicy
from app.adapters.cebeci_api_ssl import ApiSslStop

router=APIRouter(prefix='/router-registry',tags=['router-onboarding'])

def secure_panel(request:Request):
    from ipaddress import ip_address
    try:local=request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:local=False
    if request.url.scheme!='https' and not local:raise HTTPException(403,'SECURE_PANEL_TRANSPORT_REQUIRED')


def mutator(user:dict=Depends(current_admin),x_v2_demo_action:str|None=Header(default=None),_secure=Depends(secure_panel)):
    current_admin(user)
    if x_v2_demo_action!='router-onboarding':raise HTTPException(403,'Router işlemi onayı gerekli.')
    if not operator_allowed(user):raise HTTPException(403,'ONBOARDING_OPERATOR_NOT_AUTHORIZED')
    return user


def operator_allowed(user):
    from app.core.pilot_runtime import operator_in_profile
    ids={value.strip() for value in os.environ.get('V2_ROUTER_ONBOARDING_OPERATOR_IDS','').split(',') if value.strip()}
    identity=pilot_identity(user)
    return identity['state']=='ELIGIBLE' and identity['candidate']['id'] in ids and operator_in_profile(identity['candidate']['id'])


def operator_candidate(user):
    return pilot_identity(user)['candidate']


def reader(user:dict=Depends(current_admin)):
    current_admin(user)
    if not operator_allowed(user):raise HTTPException(403,'ONBOARDING_OPERATOR_NOT_AUTHORIZED')
    return user


def execute(call,*args):
    try:return call(*args)
    except RegistryError as error:raise HTTPException(error.status,error.code) from None


@router.get('/options')
def options(user:dict=Depends(current_admin)):
    try:
        policy=ConnectionPolicy.environment()
        return dict(connection_enabled=policy.enabled,operator_authorized=operator_allowed(user),operator_candidate=operator_candidate(user),pilot_identity=pilot_identity(user),source_ip=policy.source_ip or None,
            allowed_networks=list(policy.allowed_networks),allowed_ports=list(policy.allowed_ports),
            tls_required=True,pin_required=True,read_only=True,automatic_polling=False,is_demo=False)
    except ApiSslStop:raise HTTPException(503,'CONNECTION_POLICY_INVALID') from None


@router.get('')
def list_routers(query:str=Query('',max_length=120),status:str=Query('ALL',pattern='^(ALL|VERIFIED|STALE|CHECK_FAILED|PENDING_VERIFICATION)$'),
                 page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=100),user:dict=Depends(reader)):
    return execute(registry.list,query,status,page,page_size)


@router.post('/inventory')
def inventory(payload:InventoryRouter,user:dict=Depends(mutator)):
    return execute(registry.inventory,payload,user['id'])


@router.post('/verify')
def verify(payload:RouterCandidate,user:dict=Depends(mutator)):
    if 'V2_DEPLOYMENT_PROFILE' in os.environ:raise HTTPException(403,'DEDICATED_PILOT_FLOW_REQUIRED')
    return execute(registry.verify,payload,user['id'])


@router.post('/register')
def register(payload:RegisterVerified,user:dict=Depends(mutator)):
    return execute(registry.register,payload,user['id'])


@router.post('/verifications/{verification_id}/cancel')
def cancel(verification_id:str,user:dict=Depends(mutator)):
    return execute(registry.cancel,verification_id,user['id'])


@router.get('/{id}')
def detail(id:str,user:dict=Depends(reader)):
    return execute(registry.detail,id)


@router.post('/{id}/check')
def check(id:str,payload:RecheckRouter,user:dict=Depends(mutator)):
    if 'V2_DEPLOYMENT_PROFILE' in os.environ:raise HTTPException(403,'DEDICATED_PILOT_FLOW_REQUIRED')
    return execute(registry.recheck,id,payload,user['id'])

@router.post('/pilot/cebeci/verify')
def verify_cebeci(payload:CebeciPilotCandidate,user:dict=Depends(mutator)):
    return execute(registry.verify_pilot,payload,user['id'])

@router.post('/{id}/read-only')
def read_only(id:str,payload:RecheckRouter,user:dict=Depends(mutator)):
    return execute(registry.read_details,id,payload,user['id'])
