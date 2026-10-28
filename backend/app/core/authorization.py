"""One deny-by-default router scope, shared by every read and mutation route."""
from fastapi import HTTPException
from app.services.demo_data import ROUTERS
PERMISSIONS=('can_view','can_manage_pppoe','can_manage_hotspot','can_view_reports','can_use_mikajani','can_ack_alarms')
WRITE_FLAGS=('can_manage_pppoe','can_manage_hotspot','can_ack_alarms')

def is_admin(user):return user.get('role_code')=='ADMIN' or user.get('role')=='Sistem Yöneticisi'

def allowed(user,permission='can_view'):
    grants=user.get('permissions',{})
    return {r['id'] for r in ROUTERS if grants.get(r['id'],{}).get('can_view') is True and grants.get(r['id'],{}).get(permission) is True
            and (permission not in WRITE_FLAGS or is_admin(user))}

def routers_for(user,permission='can_view'):
    ids=allowed(user,permission);return [r for r in ROUTERS if r['id'] in ids]

def router_id(item):
    if item.get('router_id') is not None:return item['router_id']
    matches=[r['id'] for r in ROUTERS if r['name']==item.get('router_name')]
    return matches[0] if len(matches)==1 else None

def items_for(items,user,permission='can_view'):
    ids=allowed(user,permission);return [row for row in items if router_id(row) in ids]

def require_router(user,id,permission='can_view'):
    if id not in allowed(user):raise HTTPException(404,'Kayıt bulunamadı')
    if id not in allowed(user,permission):raise HTTPException(403,'Bu işlem için yetki gerekli')

def require_feature(user,permission):
    if not allowed(user,permission):raise HTTPException(403,'Bu işlem için yetki gerekli')

def subscriber_for(user,id,permission='can_view'):
    from app.services import demo_subscriptions
    detail=demo_subscriptions.store.detail(id)
    if not detail:raise HTTPException(404,'Kayıt bulunamadı')
    require_router(user,router_id(detail['item']),permission)
    return detail

def public_item(item,user):
    # Saved telemetry/history is a report capability, not a can_view side channel.
    return {**item,'can_manage_pppoe':router_id(item) in allowed(user,'can_manage_pppoe'),'demo_report':item.get('demo_report') if router_id(item) in allowed(user,'can_view_reports') else None}


def public_detail(detail,user):
    return {**detail,'item':public_item(detail['item'],user),
            'history':detail['history'] if router_id(detail['item']) in allowed(user,'can_view_reports') else [],
            'history_available':router_id(detail['item']) in allowed(user,'can_view_reports')}
