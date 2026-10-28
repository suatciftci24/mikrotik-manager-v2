from fastapi import APIRouter,Depends,Header,HTTPException,Query
from app.core.security import current_admin,current_demo_user
from app.services import system_settings as service
from app.services.system_health import security_policy,sources,health
from app.services.demo_subscriptions import DemoChangeError,DemoStorageUnavailable
router=APIRouter(tags=['local-system-management'])

def mutator(user:dict=Depends(current_admin),x_v2_demo_action:str|None=Header(default=None)):
    if x_v2_demo_action!='system-settings':raise HTTPException(403,'Ayar değişikliği onayı gerekli')
    return user

def handle_read(id):
    try:return service.load(id)
    except DemoChangeError as error:raise HTTPException(error.status_code,error.detail) from None
    except ValueError:raise HTTPException(503,'Kayıtlı ayar kaynağı doğrulanamadı.') from None

@router.get('/system/settings')
def get_settings(profile:str='default',user:dict=Depends(current_admin)):
    try:id=service.profile_id(profile)
    except DemoChangeError as error:raise HTTPException(error.status_code,error.detail) from None
    return {**handle_read(id),'security':security_policy(),'test_profile':id!='default'}

@router.post('/system/settings')
def save_settings(payload:service.Command,profile:str='default',user:dict=Depends(mutator)):
    try:
        id=service.profile_id(profile)
        return service.save(id,payload,user['id'])
    except DemoChangeError as error:
        if error.status_code!=404:service.rejected(profile,payload,user['id'],error)
        raise HTTPException(error.status_code,error.detail) from None
    except ValueError:raise HTTPException(503,'Kayıtlı ayar kaynağı doğrulanamadı.') from None

@router.get('/system/audit')
def audit(profile:str='default',page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=50),user:dict=Depends(current_admin)):
    try:return service.audit(service.profile_id(profile),page,page_size)
    except DemoChangeError as error:raise HTTPException(error.status_code,error.detail) from None

@router.get('/system/health')
def system_health(user:dict=Depends(current_admin)):return health(user)

@router.get('/system/sources')
def data_sources(user:dict=Depends(current_admin)):return sources()

@router.get('/preferences')
def preferences(user:dict=Depends(current_demo_user)):
    try:return service.effective(user['id'])
    except ValueError:raise HTTPException(503,'Sunum tercihleri doğrulanamadı.') from None

@router.post('/preferences')
def update_preferences(payload:service.PersonalCommand,user:dict=Depends(current_demo_user),x_v2_demo_action:str|None=Header(default=None)):
    if x_v2_demo_action!='ui-preferences':raise HTTPException(403,'Kişisel tercih onayı gerekli')
    id='user:'+user['id']
    try:return service.save(id,payload,user['id'],personal=True)
    except DemoChangeError as error:
        service.rejected(id,payload,user['id'],error)
        raise HTTPException(error.status_code,error.detail) from None

@router.get('/system/integrations')
def integration_readiness(user:dict=Depends(current_admin)):
    from app.integrations.gateway import readiness
    return readiness()

@router.get('/system/resilience')
def integration_resilience(user:dict=Depends(current_admin)):
    from app.integrations.gateway import resilience
    return resilience(user)

@router.get('/system/simulator')
def sync_simulator(page:int=Query(1,ge=1,le=1000000),page_size:int=Query(5,ge=1,le=5),user:dict=Depends(current_admin)):
    from app.simulation.report import read_report
    return read_report(user,page,page_size)

@router.get('/system/integration-management')
def integration_management(router_id:str='',page:int=Query(1,ge=1,le=1000000),page_size:int=Query(10,ge=1,le=25),user:dict=Depends(current_admin)):
    from app.integrations.planning import inventory
    return inventory(user,router_id,page,page_size)

@router.get('/system/integration-management/{router_id}')
def integration_management_detail(router_id:str,user:dict=Depends(current_admin)):
    from app.integrations.planning import detail
    return detail(user,router_id)
