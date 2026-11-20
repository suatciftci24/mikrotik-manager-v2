"""Administrator-only GET. The route has no connector or mutation dependency."""
from fastapi import APIRouter, Depends, HTTPException, Response
from app.core.security import current_admin
from app.services.device_inventory import read_inventory

router = APIRouter(prefix='/device-inventory', tags=['router-center'])

@router.get('')
def inventory(response: Response, user: dict = Depends(current_admin)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return read_inventory()
    except (OSError, ValueError):
        raise HTTPException(503, 'RouterOS gözlem kaynağı okunamadı.') from None
