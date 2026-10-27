from fastapi import APIRouter, Depends
from app.core.security import current_demo_user
from app.schemas.router_events import RouterEventList

router = APIRouter(prefix='/router-events', tags=['operations'])


@router.get('', response_model=RouterEventList)
def list_router_events(_user: dict = Depends(current_demo_user)):
    # No recorded event source exists in the current V2 demo. Inventory is not history.
    return RouterEventList()
