from fastapi import APIRouter, Depends, HTTPException
from app.schemas.details import SubscriberDetail, SubscriberList
from app.services.details import subscriber_detail
from app.core.security import current_demo_user
from app.services.demo_data import SUBSCRIBERS

router = APIRouter(prefix='/subscribers', tags=['subscriber-management'])


@router.get('', response_model=SubscriberList)
def list_subscribers(_user: dict = Depends(current_demo_user)):
    return {'items': SUBSCRIBERS, 'total': len(SUBSCRIBERS), 'is_demo': True}


@router.get('/{item_id}', response_model=SubscriberDetail)
def get_subscriber(item_id: str, _user: dict = Depends(current_demo_user)):
    detail = subscriber_detail(item_id)
    if detail is None:
        raise HTTPException(status_code=404, detail='Kayıt bulunamadı')
    return detail
