from fastapi import APIRouter,Depends,Query,Header,HTTPException,Request,Response,status
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
    if data.item.status=='PENDING_VERIFICATION':binding=None
    return snapshot(router_id, is_demo=data.is_demo, binding=binding, source=source, account_id=account_id)


from uuid import UUID
from app.schemas.subscriber_center import SubscriberSaveResult
@router.get('/subscriber-workspace/requests/{request_id}',response_model=SubscriberSaveResult)
def saved_request(request_id:UUID,user:dict=Depends(current_admin)):
    current_admin(user)
    return execute(workspace.save_result,request_id,user['id'])


from app.schemas.subscriber_management_center import OperationRequestResult
@router.get('/subscriber-workspace/management/requests/{request_id}',response_model=OperationRequestResult)
def operation_result(request_id:UUID,user:dict=Depends(current_admin)):
    current_admin(user)
    return execute(operations.request_result,request_id,user['id'])

@router.get('/subscriber-workspace/renewals/requests/{request_id}',response_model=SubscriberSaveResult)
def renewal_result(request_id:UUID,user:dict=Depends(current_admin)):
    current_admin(user)
    return execute(workspace.renewal_result,request_id,user['id'])


from app.services.subscriber_photos import PhotoError,SubscriberPhotoStore
from app.schemas.subscriber_photos import SubscriberPhotoCollection,SubscriberPhotoCreated,SubscriberPhotoDeleted
from starlette.concurrency import run_in_threadpool

photo_store=SubscriberPhotoStore()

def photo_subject(item_id:str,user:dict,write:bool=False):
    if item_id.startswith('demo-managed-sub-'):
        current_admin(user)
        data=execute(workspace.detail,item_id)
        if data.source!='PERSISTENT_WORKSPACE' or data.persistence!='local-postgresql-workspace' or data.item.id!=item_id:
            raise HTTPException(404,'Sentetik abone bulunamadı.')
        item=data.item.model_dump(mode='json')
    else:
        if not item_id.startswith('demo-sub-'):
            raise HTTPException(404,'Sentetik abone bulunamadı.')
        record=subscriber_for(user,item_id)
        item=record.get('item',{})
        if (record.get('is_demo') is not True or record.get('persistence')!='process-memory'
                or item.get('id')!=item_id):raise HTTPException(404,'Sentetik abone bulunamadı.')
        if write:
            permission='can_manage_hotspot' if item.get('access_type')=='HOTSPOT' else 'can_manage_pppoe'
            subscriber_for(user,item_id,permission)
    source=item.get('source');access_type=item.get('access_type');router_id=item.get('router_id')
    if source not in ('LOCAL','RADIUS') or access_type not in ('PPPOE','HOTSPOT') or not router_id:
        raise HTTPException(409,'Abonenin router, yetkili kaynak veya erişim türü doğrulanamadı.')
    if item.get('router_missing') is True or item.get('router_source')=='UNKNOWN':
        raise HTTPException(409,'Abonenin sentetik router bağı doğrulanamadı.')
    return {'id':item_id,'source':source,'access_type':access_type,'router_id':router_id}

def photo_error(error:PhotoError):
    raise HTTPException(error.status,error.detail) from None

def require_photo_action(user:dict,action:str|None):
    if action!='subscriber-photos':raise HTTPException(403,'Abone fotoğrafı işlemi için açık onay gerekli.')
    return user

@router.get('/subscriber-center/{id}/photos',response_model=SubscriberPhotoCollection)
def subscriber_photos(id:str,user:dict=Depends(current_demo_user)):
    subject=photo_subject(id,user)
    try:items=photo_store.list(id,subject['source'],subject['access_type'])
    except PhotoError as error:photo_error(error)
    return {'subscriber_id':id,'source':subject['source'],'access_type':subject['access_type'],'items':items,'is_demo':True}

@router.post('/subscriber-center/{id}/photos',response_model=SubscriberPhotoCreated,status_code=status.HTTP_201_CREATED)
async def upload_subscriber_photo(id:str,request:Request,user:dict=Depends(current_demo_user),x_v2_demo_action:str|None=Header(default=None)):
    require_photo_action(user,x_v2_demo_action)
    subject=photo_subject(id,user,write=True)
    length=request.headers.get('content-length')
    if length:
        try:
            if int(length)>10*1024*1024:raise HTTPException(413,'Fotoğraf 10 MiB sınırını aşıyor.')
        except ValueError:raise HTTPException(400,'İstek boyutu doğrulanamadı.') from None
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>10*1024*1024:raise HTTPException(413,'Fotoğraf 10 MiB sınırını aşıyor.')
        data.extend(chunk)
    try:item=await run_in_threadpool(photo_store.add,id,subject['source'],subject['access_type'],user['id'],bytes(data))
    except PhotoError as error:photo_error(error)
    return {'item':item,'is_demo':True}

@router.get('/subscriber-center/{id}/photos/{photo_id}')
def read_subscriber_photo(id:str,photo_id:str,variant:str=Query('thumbnail',pattern='^(thumbnail|full)$'),user:dict=Depends(current_demo_user)):
    subject=photo_subject(id,user)
    try:data=photo_store.read(id,subject['source'],subject['access_type'],photo_id,variant=='thumbnail')
    except PhotoError as error:photo_error(error)
    return Response(data,media_type='image/jpeg',headers={'Cache-Control':'private, no-store','Vary':'Cookie','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox",'Referrer-Policy':'no-referrer','Content-Disposition':'inline; filename="subscriber-photo.jpg"'})

@router.delete('/subscriber-center/{id}/photos/{photo_id}',response_model=SubscriberPhotoDeleted)
def delete_subscriber_photo(id:str,photo_id:str,user:dict=Depends(current_demo_user),x_v2_demo_action:str|None=Header(default=None)):
    require_photo_action(user,x_v2_demo_action)
    subject=photo_subject(id,user,write=True)
    try:photo_store.delete(id,subject['source'],subject['access_type'],photo_id)
    except PhotoError as error:photo_error(error)
    return {'id':photo_id,'deleted':True,'is_demo':True}
