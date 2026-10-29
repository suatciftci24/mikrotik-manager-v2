"""One ID-based, read-only view; every source keeps its original authorization boundary."""
from fastapi import APIRouter,Depends,HTTPException
from app.core.security import current_demo_user,current_admin
from app.core.authorization import require_router
from app.api.v1.router_registry import reader as registry_reader,execute as registry_execute
from app.api.v1.router_workspace import execute as workspace_execute
from app.services.router_registry import registry
from app.services.router_workspace import workspace
from app.services.demo_data import ROUTERS
from app.services.router_center import persistent_demo,registered,static_demo
from app.schemas.router_center import RouterCenterData

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
