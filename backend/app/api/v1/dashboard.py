from app.core.authorization import routers_for,items_for
"""Compatibility summary projected from the same saved inventory as the panel."""
from fastapi import APIRouter, Depends
from app.core.security import current_demo_user
from app.services.workspace_inventory import persistent_inventory,router_choices
from app.core.security import current_admin
from app.api.v1.router_workspace import execute
from app.services import demo_subscriptions

router = APIRouter(prefix='/dashboard', tags=['operations'])


@router.get('/summary')
def dashboard_summary(_user: dict = Depends(current_demo_user)):
    if persistent_inventory():
        current_admin(_user)
        from app.services.subscriber_center import workspace
        routers=execute(router_choices)
        first=execute(workspace.list, '', 'ALL', 'ALL', '', 1, 100)
        total=first['total']
        accounts=list(first['items'])
        for page in range(2,(total+99)//100+1):
            accounts.extend(execute(workspace.list,'','ALL','ALL','',page,100)['items'])
        return {'summary':{'router_count':len(routers),'routers_online':None,
            'subscribers_total':total,'subscribers_online':None,
            'radius_accounts':sum(row.source=='RADIUS' for row in accounts),
            'local_accounts':sum(row.source=='LOCAL' for row in accounts),
            'monthly_revenue':None,'attention_count':None},
            'traffic':None,'activity':None,'attention':None,'is_demo':True}
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
