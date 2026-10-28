from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import current_admin,current_user_mutator
from app.services import identity
from app.services.demo_subscriptions import DemoChangeError
from app.services.demo_data import ROUTERS
router=APIRouter(prefix='/users',tags=['local-user-management'])

@router.get('')
def users(page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=50),query:str=Query('',max_length=100),user:dict=Depends(current_admin)):
    return {**identity.list_users(page,page_size,query),'routers':[dict(id=r['id'],name=r['name']) for r in ROUTERS]}

@router.get('/audit')
def audit(page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=50),user:dict=Depends(current_admin)):
    return identity.audit_users(page,page_size)

@router.post('')
def create(payload:identity.UserCreate,user:dict=Depends(current_user_mutator)):
    try:return identity.save_user(payload,user['id'])
    except DemoChangeError as error:
        identity.record_rejection(payload,user['id'],None,'CREATE',error)
        raise HTTPException(error.status_code,error.detail) from None

@router.post('/{user_id}')
def update(user_id:str,payload:identity.UserChange,user:dict=Depends(current_user_mutator)):
    try:return identity.save_user(payload,user['id'],user_id)
    except DemoChangeError as error:
        identity.record_rejection(payload,user['id'],user_id,'UPDATE',error)
        raise HTTPException(error.status_code,error.detail) from None

@router.get('/{user_id}')
def detail(user_id:str,user:dict=Depends(current_admin)):
    record=identity.find_user(user_id)
    if record is None:raise HTTPException(404,'Kayıt bulunamadı')
    return identity.public_user(record,True)
