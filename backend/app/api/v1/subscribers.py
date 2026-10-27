from fastapi import APIRouter, Depends, HTTPException
from app.schemas.details import SubscriberDetail, SubscriberList
from app.services.details import subscriber_detail
from app.core.security import current_demo_user, current_demo_mutator, current_demo_account_mutator
from app.services import demo_subscriptions
from app.schemas.subscriber_events import ExpiryChange
from app.schemas.subscriber_management import SubscriberCreate, SubscriberChange, DemoOptions
from app.services.demo_management import demo_plans
from app.services.demo_data import ROUTERS

router = APIRouter(prefix='/subscribers', tags=['subscriber-management'])


@router.get('', response_model=SubscriberList)
def list_subscribers(_user: dict = Depends(current_demo_user)):
    items = demo_subscriptions.store.list_items()
    return {'items': items, 'total': len(items), 'is_demo': True}


def require_persistent_store():
    if getattr(demo_subscriptions.store, 'persistence', None) != 'local-postgresql-demo' and not isinstance(demo_subscriptions.store, demo_subscriptions.ConfiguredDemoStore):
        raise HTTPException(status_code=503, detail='Bu işlem yalnız izole V2 PostgreSQL demo deposunda kullanılabilir.')


@router.get('/demo-options', response_model=DemoOptions)
def demo_options(_user: dict = Depends(current_demo_user)):
    require_persistent_store()
    demo_subscriptions.store.ping()
    return {'plans': demo_plans(), 'routers': [{'id': r['id'], 'name': r['name']} for r in ROUTERS if r['is_demo']],
            'is_demo': True, 'persistence': 'local-postgresql-demo'}


@router.post('/demo-create', response_model=SubscriberDetail)
def create_demo_subscriber(payload: SubscriberCreate, user: dict = Depends(current_demo_account_mutator)):
    require_persistent_store()
    try:
        return demo_subscriptions.store.create_subscriber(payload, user['id'])
    except demo_subscriptions.DemoChangeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post('/{item_id}/demo-management', response_model=SubscriberDetail)
def change_demo_subscriber(item_id: str, payload: SubscriberChange, user: dict = Depends(current_demo_account_mutator)):
    require_persistent_store()
    try:
        return demo_subscriptions.store.change_subscriber(item_id, payload, user['id'])
    except demo_subscriptions.DemoChangeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


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
