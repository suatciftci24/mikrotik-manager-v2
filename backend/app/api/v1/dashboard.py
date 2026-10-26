from fastapi import APIRouter, Depends
from app.core.security import current_demo_user
from app.services.demo_data import DASHBOARD

router = APIRouter(prefix='/dashboard', tags=['operations'])


@router.get('/summary')
def dashboard_summary(_user: dict = Depends(current_demo_user)):
    return DASHBOARD
