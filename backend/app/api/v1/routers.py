from fastapi import APIRouter, Depends, HTTPException
from app.schemas.details import RouterDetail, RouterRecord
from app.services.details import router_detail
from app.core.security import current_demo_user
from app.services.demo_data import ROUTERS

router = APIRouter(prefix='/routers', tags=['router-management'])


@router.get('')
def list_routers(_user: dict = Depends(current_demo_user)):
    return {'items': [RouterRecord.model_validate(row).model_dump(mode='json') for row in ROUTERS], 'total': len(ROUTERS), 'is_demo': True}


@router.get('/{item_id}', response_model=RouterDetail)
def get_router(item_id: str, _user: dict = Depends(current_demo_user)):
    detail = router_detail(item_id)
    if detail is None:
        raise HTTPException(status_code=404, detail='Kayıt bulunamadı')
    return detail
