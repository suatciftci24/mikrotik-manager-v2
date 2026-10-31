"""One ID-based, read-only view; every source keeps its original authorization boundary."""
from fastapi import APIRouter,Depends,HTTPException,Query
from app.core.security import current_demo_user,current_admin
from app.core.authorization import require_router
from app.api.v1.router_registry import reader as registry_reader,execute as registry_execute
from app.api.v1.router_workspace import execute as workspace_execute
from app.services.router_registry import registry
from app.services.router_workspace import workspace
from app.services.demo_data import ROUTERS
from app.services.router_center import persistent_demo,registered,static_demo
from app.schemas.router_center import RouterCenterData
from app.schemas.subscriber_center import RouterSubscriberList
from app.services.pppoe_readonly import PppoeSnapshot, disabled_binding, snapshot

router=APIRouter(prefix='/router-center',tags=['router-center'])

@router.get('/{id}',response_model=RouterCenterData)
def detail(id:str,user:dict=Depends(current_demo_user)):
    if id.startswith('demo-managed-router-'):
        current_admin(user)
        row,events=workspace_execute(workspace.center_detail,id)
        return persistent_demo(row,events)
    if id.startswith('registered-'):
        registry_reader(user)
        data=registry_execute(registry.detail,id)
        return registered(data['item'],data['history'])
    require_router(user,id)
    row=next((row for row in ROUTERS if row['id']==id),None)
    if row is None:raise HTTPException(404,'Router bulunamadı.')
    return static_demo(row)

@router.get('/{id}/subscribers',response_model=RouterSubscriberList)
def subscribers(id:str,access_type:str=Query(...,pattern='^(PPPOE|HOTSPOT)$'),query:str=Query('',max_length=120),status:str=Query('ALL',pattern='^(ALL|ACTIVE|PAUSED|PENDING)$'),page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=100),user:dict=Depends(current_demo_user)):
    from app.services.subscriber_center import workspace as accounts,legacy_center
    if id.startswith('demo-managed-router-'):
        current_admin(user)
        result=workspace_execute(accounts.list,query,access_type,status,id,page,page_size,True)
        return {**result,'source':'PERSISTENT_WORKSPACE','availability':'AVAILABLE'}
    if id.startswith('registered-'):
        registry_reader(user);registry_execute(registry.detail,id)
        return dict(items=[],total=None,page=page,page_size=page_size,is_demo=False,source='REGISTERED',availability='PREPARING')
    require_router(user,id)
    from app.services import demo_subscriptions
    rows=[row for row in demo_subscriptions.store.list_items() if row.get('is_demo') is True and row.get('router_id')==id and row.get('access_type')==access_type and (status=='ALL' or row.get('status')==status) and (not query or query.casefold() in (row.get('username','')+' '+row.get('customer_name','')).casefold())]
    return dict(items=[legacy_center({'item':row}).item for row in rows[(page-1)*page_size:page*page_size]],total=len(rows),page=page,page_size=page_size,is_demo=True,source='LEGACY_DEMO',availability='AVAILABLE')


@router.get('/{id}/pppoe-observations', response_model=PppoeSnapshot)
def pppoe_observations(id: str, user: dict = Depends(current_demo_user), binding=Depends(disabled_binding)):
    # Reuse the center's source-specific authorization before any adapter dispatch.
    data = detail(id, user)
    return snapshot(id, is_demo=data.is_demo, binding=binding)
