from fastapi import APIRouter,Depends,Query,Header,HTTPException
from app.core.security import current_demo_user,current_admin
from app.core.authorization import subscriber_for,public_detail
from app.api.v1.router_workspace import execute
from app.services.subscriber_center import workspace,legacy_center
from app.schemas.subscriber_center import SubscriberCenterData,SubscriberWorkspaceList,CenterSubscriber,SyntheticSubscriberCommand,SubscriberRenewal

router=APIRouter(tags=['subscriber-center'])
def mutator(user:dict=Depends(current_admin),x_v2_demo_action:str|None=Header(default=None)):
    current_admin(user)
    if x_v2_demo_action!='subscriber-workspace':raise HTTPException(403,'Sentetik abone işlem onayı gerekli.')
    return user
@router.get('/subscriber-center/{id}',response_model=SubscriberCenterData)
def detail(id:str,user:dict=Depends(current_demo_user)):
    if id.startswith('demo-managed-sub-'):
        current_admin(user);return execute(workspace.detail,id)
    try:return legacy_center(public_detail(subscriber_for(user,id),user))
    except HTTPException as failure:
        if failure.status_code!=404:raise
        # Only a central admin may inspect an orphan; restricted viewers retain 404.
        try:current_admin(user)
        except HTTPException:raise failure from None
        from app.services import demo_subscriptions
        from app.services.demo_data import ROUTERS
        detail=demo_subscriptions.store.detail(id)
        if not detail or detail['item'].get('is_demo') is not True or detail['item'].get('router_id') in {r['id'] for r in ROUTERS}:raise failure
        return legacy_center(detail)
@router.get('/subscriber-workspace',response_model=SubscriberWorkspaceList)
def list_subscribers(query:str=Query('',max_length=120),access_type:str=Query('ALL',pattern='^(ALL|PPPOE|HOTSPOT)$'),status:str=Query('ALL',pattern='^(ALL|ACTIVE|PAUSED)$'),router_id:str=Query('',max_length=100),page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=100),user:dict=Depends(current_admin)):
    return execute(workspace.list,query,access_type,status,router_id,page,page_size)
@router.post('/subscriber-workspace',response_model=CenterSubscriber)
def create(payload:SyntheticSubscriberCommand,user:dict=Depends(mutator)):return execute(workspace.save,payload,user['id'])
@router.post('/subscriber-workspace/{id}',response_model=CenterSubscriber)
def update(id:str,payload:SyntheticSubscriberCommand,user:dict=Depends(mutator)):return execute(workspace.save,payload,user['id'],id)

@router.post('/subscriber-workspace/{id}/renew',response_model=CenterSubscriber)
def renew(id:str,payload:SubscriberRenewal,user:dict=Depends(mutator)):return execute(workspace.renew,id,payload,user['id'])

from app.schemas.subscriber_management_center import SubscriberOperations,OperationResults,OperationHistory
from app.services.subscriber_operations import operations

@router.post('/subscriber-workspace/management/execute',response_model=OperationResults)
def manage(payload:SubscriberOperations,user:dict=Depends(mutator)):
    return {'results':[operations.execute(entry,user['id']) for entry in payload.entries],'is_demo':True}

@router.get('/subscriber-workspace/management/history',response_model=OperationHistory)
def history(item_id:str=Query('',max_length=64),operation:str=Query('ALL',pattern='^(ALL|EDIT|PLAN|STATUS|EXPIRE|EXTEND|ROUTER|CREATE|UPDATE|RENEWAL)$'),result:str=Query('ALL',pattern='^(ALL|SUCCESS|FAILED)$'),page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=100),user:dict=Depends(current_admin)):
    return execute(operations.history,item_id,operation,result,page,page_size)


from typing import Literal
from app.services.pppoe_readonly import PppoeSnapshot, disabled_binding, snapshot

@router.get('/subscriber-observations/{router_id}/{account_id}', response_model=PppoeSnapshot)
def pppoe_observations(router_id: str, account_id: str, source: Literal['LOCAL', 'RADIUS'],
                       user: dict = Depends(current_demo_user), binding=Depends(disabled_binding)):
    # Real IDs come only from the server-side binding, never the demo workspace.
    from app.api.v1.router_center import detail as router_detail
    data = router_detail(router_id, user)
    return snapshot(router_id, is_demo=data.is_demo, binding=binding, source=source, account_id=account_id)
