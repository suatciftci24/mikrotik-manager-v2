from app.core.authorization import routers_for,require_router,public_item,allowed
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.details import RouterDetail, RouterRecord
from app.services.details import router_detail
from app.core.security import current_demo_user
from app.services.demo_data import ROUTERS

router = APIRouter(prefix='/routers', tags=['router-management'])


@router.get('')
def list_routers(_user: dict = Depends(current_demo_user)):
    rows=routers_for(_user)
    return {'items': [RouterRecord.model_validate(row).model_dump(mode='json') for row in rows], 'total': len(rows), 'is_demo': True}


@router.get('/{item_id}', response_model=RouterDetail)
def get_router(item_id: str, _user: dict = Depends(current_demo_user)):
    require_router(_user,item_id)
    detail = router_detail(item_id)
    if detail is None:
        raise HTTPException(status_code=404, detail='Kayıt bulunamadı')
    return {**detail,'item':{**detail['item'],'wan_snapshot':detail['item'].get('wan_snapshot') if item_id in allowed(_user,'can_view_reports') else None},'assigned_subscribers':[public_item(row,_user) for row in detail['assigned_subscribers']]}

@router.get('/{item_id}/provider-snapshot')
def provider_snapshot(item_id:str,page:int=1,page_size:int=25,_user:dict=Depends(current_demo_user)):
    from app.integrations.gateway import read_router
    return read_router(_user,item_id,page=page,page_size=page_size)
