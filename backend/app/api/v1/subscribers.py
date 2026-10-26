from fastapi import APIRouter, Depends
from app.core.security import current_demo_user
from app.services.demo_data import SUBSCRIBERS

router = APIRouter(prefix='/subscribers', tags=['subscriber-management'])


@router.get('')
def list_subscribers(_user: dict = Depends(current_demo_user)):
    return {'items': SUBSCRIBERS, 'total': len(SUBSCRIBERS), 'is_demo': True}
