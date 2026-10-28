from app.core.authorization import items_for,routers_for,public_item,public_detail,subscriber_for,require_router,require_feature
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.details import SubscriberDetail, SubscriberList, QuickBatchResponse
from app.services.details import subscriber_detail
from app.core.security import current_demo_user, current_demo_mutator, current_demo_account_mutator
from app.services import demo_subscriptions
from app.schemas.subscriber_events import ExpiryChange, QuickBatch
from app.schemas.subscriber_management import SubscriberCreate, SubscriberChange, DemoOptions
from app.services.demo_management import demo_plans
from app.services.demo_data import ROUTERS

router = APIRouter(prefix='/subscribers', tags=['subscriber-management'])


@router.get('', response_model=SubscriberList)
def list_subscribers(_user: dict = Depends(current_demo_user)):
    items = [public_item(row,_user) for row in items_for(demo_subscriptions.store.list_items(),_user)]
    return {'items': items, 'total': len(items), 'is_demo': True}


def require_persistent_store():
    if getattr(demo_subscriptions.store, 'persistence', None) != 'local-postgresql-demo' and not isinstance(demo_subscriptions.store, demo_subscriptions.ConfiguredDemoStore):
        raise HTTPException(status_code=503, detail='Bu işlem yalnız izole V2 PostgreSQL demo deposunda kullanılabilir.')


@router.get('/demo-options', response_model=DemoOptions)
def demo_options(_user: dict = Depends(current_demo_user)):
    require_feature(_user,'can_manage_pppoe')
    require_persistent_store()
    demo_subscriptions.store.ping()
    return {'plans': demo_plans(), 'routers': [{'id': r['id'], 'name': r['name']} for r in routers_for(_user,'can_manage_pppoe') if r['is_demo']],
            'is_demo': True, 'persistence': 'local-postgresql-demo'}


@router.post('/demo-create', response_model=SubscriberDetail)
def create_demo_subscriber(payload: SubscriberCreate, user: dict = Depends(current_demo_account_mutator)):
    require_router(user,payload.router_id,'can_manage_pppoe')
    require_persistent_store()
    try:
        return public_detail(demo_subscriptions.store.create_subscriber(payload, user['id']),user)
    except demo_subscriptions.DemoChangeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post('/{item_id}/demo-management', response_model=SubscriberDetail)
def change_demo_subscriber(item_id: str, payload: SubscriberChange, user: dict = Depends(current_demo_account_mutator)):
    subscriber_for(user,item_id,'can_manage_pppoe')
    require_persistent_store()
    try:
        return public_detail(demo_subscriptions.store.change_subscriber(item_id, payload, user['id']),user)
    except demo_subscriptions.DemoChangeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get('/{item_id}', response_model=SubscriberDetail)
def get_subscriber(item_id: str, _user: dict = Depends(current_demo_user)):
    return public_detail(subscriber_for(_user,item_id),_user)


@router.post('/{item_id}/demo-expiry', response_model=SubscriberDetail)
def change_demo_expiry(item_id: str, payload: ExpiryChange, user: dict = Depends(current_demo_mutator)):
    subscriber_for(user,item_id,'can_manage_pppoe')
    try:
        return public_detail(demo_subscriptions.store.change_expiry(item_id, payload, user['id']),user)
    except demo_subscriptions.DemoChangeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post('/demo-quick', response_model=QuickBatchResponse)
def quick_batch(payload: QuickBatch, user: dict = Depends(current_demo_mutator)):
    entries = payload.entries
    if len({e.item_id for e in entries}) != len(entries) or len({str(e.change.request_id) for e in entries}) != len(entries):
        raise HTTPException(422, 'Tekrarlanan abone veya işlem kimliği.')
    if len(entries) > 1 and (len({e.change.router_id for e in entries}) != 1 or any(e.change.action != 'EXTEND' for e in entries)):
        raise HTTPException(422, 'Toplu işlem yalnız aynı router üzerinde uzatma içindir.')
    for entry in entries:
        if entry.change.action=='CREATE':require_router(user,entry.change.router_id,'can_manage_pppoe')
        else:subscriber_for(user,entry.item_id,'can_manage_pppoe')
    results = []
    for entry in entries:
        if entry.change.action == 'CREATE' and entry.item_id != f'demo-sub-{entry.change.request_id}':
            raise HTTPException(422, 'Sentetik oluşturma kimliği geçersiz.')
        try:
            result = demo_subscriptions.store.change_expiry(entry.item_id, entry.change, user['id'])
            results.append({'item_id': entry.item_id, 'success': True, 'result': public_detail(result,user)})
        except demo_subscriptions.DemoChangeError as error:
            results.append({'item_id': entry.item_id, 'success': False, 'status': error.status_code, 'error': error.detail})
        except demo_subscriptions.DemoStorageUnavailable:
            results.append({'item_id': entry.item_id, 'success': False, 'status': 503, 'error': 'Demo saklama erişilemiyor; aynı isteği tekrar deneyin.'})
    return {'results': results, 'is_demo': True}
