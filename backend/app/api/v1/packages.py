from typing import Literal
from fastapi import APIRouter,Depends,Header,HTTPException,Query
from app.core.security import current_demo_user,current_admin
from app.core.authorization import workspace_scope
from app.api.v1.router_workspace import execute
from app.schemas.package import PackageCommand,PackageConfirmation,PackageDeletion,PackageRecord,PackageList
from app.services.packages import packages

router=APIRouter(prefix='/packages',tags=['synthetic-business-packages'])

def mutator(user:dict=Depends(current_admin),x_v2_demo_action:str|None=Header(default=None)):
    current_admin(user)
    if x_v2_demo_action!='package-workspace':raise HTTPException(403,'Sentetik paket işlem onayı gerekli.')
    return user

@router.get('',response_model=PackageList)
def listing(page:int=Query(1,ge=1,le=1000000),page_size:int=Query(100,ge=1,le=100),include_inactive:bool=False,query:str=Query('',max_length=120),
            status:Literal['ALL','ACTIVE','INACTIVE']='ALL',user:dict=Depends(current_demo_user)):
    scope=workspace_scope(user)
    if include_inactive or status=='INACTIVE':current_admin(user)
    if scope is not None and not scope:raise HTTPException(403,'Paket görüntüleme için router kapsamı gerekli.')
    return execute(packages.list,page,page_size,include_inactive or status=='INACTIVE',query=query,status=status)

@router.post('',response_model=PackageRecord)
def create(payload:PackageCommand,user:dict=Depends(mutator)):return execute(packages.save,payload,user['id'])

@router.post('/{id}',response_model=PackageRecord)
def update(id:str,payload:PackageCommand,user:dict=Depends(mutator)):return execute(packages.save,payload,user['id'],id)

@router.delete('/{id}',response_model=PackageDeletion)
def delete(id:str,payload:PackageConfirmation,user:dict=Depends(mutator)):
    return execute(packages.delete,id,payload,user['id'])

@router.get('/{id}/audit')
def audit(id:str,user:dict=Depends(current_admin)):return execute(packages.history,id)
