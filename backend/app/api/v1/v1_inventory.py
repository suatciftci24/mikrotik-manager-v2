"""Dedicated GET-only real inventory boundary; demo sources are never substituted."""
from fastapi import APIRouter, Depends, HTTPException
from app.core.security import current_admin
from app.adapters.v1_inventory import read_inventory, InventoryUnavailable

router = APIRouter(prefix='/v1-inventory', tags=['router-center'])

@router.get('')
def inventory(user: dict = Depends(current_admin)):
    try:
        return read_inventory()
    except InventoryUnavailable:
        raise HTTPException(503, 'Gerçek envanter kaynağı okunamadı; veri gösterilmiyor.') from None
