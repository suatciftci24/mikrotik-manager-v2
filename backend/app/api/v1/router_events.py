from app.core.authorization import items_for,require_feature
from fastapi import APIRouter, Depends
from app.core.security import current_demo_user
from app.schemas.router_events import RouterEventList
from app.services.demo_reports import router_event_records
from app.services import demo_subscriptions

router = APIRouter(prefix='/router-events', tags=['operations'])


@router.get('', response_model=RouterEventList)
def list_router_events(_user: dict = Depends(current_demo_user)):
    require_feature(_user,'can_view_reports')
    return router_event_records(items_for(demo_subscriptions.store.list_items(),_user,'can_view_reports'))
