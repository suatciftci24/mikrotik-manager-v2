from fastapi import APIRouter, Depends, HTTPException
from app.schemas.details import SubscriberDetail, SubscriberList
from app.services.details import subscriber_detail
from app.core.security import current_demo_user, current_demo_mutator
from app.services import demo_subscriptions
from app.schemas.subscriber_events import ExpiryChange

router = APIRouter(prefix='/subscribers', tags=['subscriber-management'])


@router.get('', response_model=SubscriberList)
def list_subscribers(_user: dict = Depends(current_demo_user)):
    items = demo_subscriptions.store.list_items()
    return {'items': items, 'total': len(items), 'is_demo': True}


@router.get('/{item_id}', response_model=SubscriberDetail)
def get_subscriber(item_id: str, _user: dict = Depends(current_demo_user)):
    detail = subscriber_detail(item_id)
    if detail is None:
        raise HTTPException(status_code=404, detail='Kayıt bulunamadı')
    return detail


@router.post('/{item_id}/demo-expiry', response_model=SubscriberDetail)
def change_demo_expiry(item_id: str, payload: ExpiryChange, user: dict = Depends(current_demo_mutator)):
    try:
        return demo_subscriptions.store.change_expiry(item_id, payload, user['id'])
    except demo_subscriptions.DemoChangeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
