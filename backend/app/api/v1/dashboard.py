from app.core.authorization import routers_for,items_for
"""Compatibility summary projected from the same saved inventory as the panel."""
from fastapi import APIRouter, Depends
from app.core.security import current_demo_user
from app.services.demo_data import ROUTERS
from app.services import demo_subscriptions

router = APIRouter(prefix='/dashboard', tags=['operations'])


@router.get('/summary')
def dashboard_summary(_user: dict = Depends(current_demo_user)):
    items = items_for(demo_subscriptions.store.list_items(),_user)
    routers=routers_for(_user)
    # Inventory counts are not active sessions, measured traffic or recorded events.
    return {
        'summary': {
            'router_count': len(routers),
            'routers_online': sum(row['status'] == 'ONLINE' for row in routers),
            'subscribers_total': len(items),
            'subscribers_online': None,
            'radius_accounts': sum(row.get('source') == 'RADIUS' for row in items),
            'local_accounts': sum(row.get('source') == 'LOCAL' for row in items),
            'monthly_revenue': sum(row['monthly_price'] for row in items),
            'attention_count': sum(row['status'] in ('OFFLINE', 'DEGRADED') for row in routers),
        },
        'traffic': None, 'activity': None, 'attention': None, 'is_demo': True,
    }
