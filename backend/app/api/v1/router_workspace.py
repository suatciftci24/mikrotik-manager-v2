"""Scoped synthetic reads; mutations and trust profiles remain central ADMIN only."""
from typing import Literal
from app.schemas.router_center import RouterCenterEvent
from fastapi import APIRouter,Depends,Header,HTTPException,Query
from app.core.security import current_admin,current_demo_user
from app.core.authorization import workspace_scope,require_workspace_router
from app.schemas.router_workspace import DemoRouterCommand,TrustProfileCommand,DeleteWorkspaceRecord,WorkspaceList,WorkspaceRecord
from app.services.router_workspace import workspace,WorkspaceError

router=APIRouter(prefix='/router-workspace',tags=['router-workspace'])
def mutator(user:dict=Depends(current_admin),x_v2_demo_action:str|None=Header(default=None)):
    current_admin(user)
    if x_v2_demo_action!='router-workspace':raise HTTPException(403,'Yerel çalışma alanı işlem onayı gerekli.')
    return user

def execute(call,*args,**kwargs):
    try:return call(*args,**kwargs)
    except WorkspaceError as error:raise HTTPException(error.status,error.detail) from None

@router.get('/routers',response_model=WorkspaceList)
def routers(query:str=Query('',max_length=120),page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=100),user:dict=Depends(current_demo_user),
            management_status:Literal['ACTIVE','INACTIVE']|None=None,
            simulated_status:Literal['ONLINE','OFFLINE','UNKNOWN']|None=None):
    scope=workspace_scope(user)
    return execute(workspace.list,'DEMO_ROUTER',query,page,page_size,scope,
                   management_status=management_status,simulated_status=simulated_status)

@router.get('/deleted-routers/history',response_model=list[RouterCenterEvent])
def deleted_history(user:dict=Depends(current_admin)):
    return execute(workspace.deleted_history)
@router.get('/routers/{id}',response_model=WorkspaceRecord)
def detail(id:str,user:dict=Depends(current_demo_user)):
    require_workspace_router(user,id)
    return execute(workspace.detail,id,'DEMO_ROUTER')
@router.post('/routers',response_model=WorkspaceRecord)
def create(payload:DemoRouterCommand,user:dict=Depends(mutator)):return execute(workspace.save,'DEMO_ROUTER',payload,user['id'])
@router.post('/routers/{id}',response_model=WorkspaceRecord)
def update(id:str,payload:DemoRouterCommand,user:dict=Depends(mutator)):return execute(workspace.save,'DEMO_ROUTER',payload,user['id'],id)
@router.post('/routers/{id}/delete')
def delete(id:str,payload:DeleteWorkspaceRecord,user:dict=Depends(mutator)):return execute(workspace.delete,id,'DEMO_ROUTER',payload,user['id'])
@router.get('/profiles',response_model=WorkspaceList)
def profiles(page:int=Query(1,ge=1,le=1000000),page_size:int=Query(100,ge=1,le=100),user:dict=Depends(current_admin)):return execute(workspace.list,'TRUST_PROFILE','',page,page_size)
@router.post('/profiles',response_model=WorkspaceRecord)
def profile(payload:TrustProfileCommand,user:dict=Depends(mutator)):return execute(workspace.save,'TRUST_PROFILE',payload,user['id'])
@router.post('/profiles/{id}/delete')
def delete_profile(id:str,payload:DeleteWorkspaceRecord,user:dict=Depends(mutator)):return execute(workspace.delete,id,'TRUST_PROFILE',payload,user['id'])
