from fastapi import APIRouter, Depends
from app.core.security import current_demo_user
from app.services.demo_data import ROUTERS

router = APIRouter(prefix='/routers', tags=['router-management'])


@router.get('')
def list_routers(_user: dict = Depends(current_demo_user)):
    return {'items': ROUTERS, 'total': len(ROUTERS), 'is_demo': True}
