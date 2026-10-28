from app.core.authorization import routers_for,items_for,require_feature,require_router,allowed,router_id as item_router_id
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import current_demo_user
from app.services import demo_subscriptions
from app.services.demo_data import ROUTERS
from app.services.operation_reports import report_range, project_report

router=APIRouter(prefix='/reports',tags=['read-only-reports'],dependencies=[Depends(current_demo_user)])


@router.get('/operations')
def operations(start:str,end:str,category:Literal['AUDIT','CONNECTION','MIKA']='AUDIT',router_id:str='',
               subscriber_id:str='',operation:Literal['','CREATE','PLAN_CHANGE','STATUS_CHANGE','RENEWAL','DATE_EDIT']='',
               priority:Literal['ALL','P1','P2','P3','P4']='ALL',state:Literal['ALL','ACTIVE','OPEN','UPDATED','RECOVERING','RESOLVED']='ALL',
               page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=50),user:dict=Depends(current_demo_user)):
    try:
        bounds=report_range(start,end,datetime.now(timezone.utc))
    except ValueError as error:raise HTTPException(422,str(error)) from None
    require_feature(user,'can_view_reports')
    scope=routers_for(user,'can_view_reports')
    if category=='MIKA':scope=[r for r in scope if r['id'] in allowed(user,'can_use_mikajani')]
    if category=='MIKA' and not scope:raise HTTPException(403,'MikAjanı rapor yetkisi gerekli')
    if router_id:
        require_router(user,router_id,'can_view_reports')
        if router_id not in {r['id'] for r in scope}:raise HTTPException(403,'Rapor yetkisi gerekli')
    selected=next((r for r in scope if r['id']==router_id),None)
    if router_id and selected is None:raise HTTPException(422,'Bilinmeyen sentetik router.')
    items,audits,total,groups=demo_subscriptions.store.report_records(*bounds,router_id,selected['name'] if selected else '',subscriber_id,operation,page_size,(page-1)*page_size,scope)
    items=[row for row in items_for(items,user,'can_view_reports') if any(r['id']==item_router_id(row) for r in scope)]
    if subscriber_id and subscriber_id not in {row['id'] for row in items}:raise HTTPException(404,'Kayıt bulunamadı')
    # Subscriber scope belongs only to the audit view; other categories remain router/date scoped.
    try:return project_report(items,scope,audits,total,groups,bounds,category,router_id,priority,state,page,page_size,[r for r in scope if r['id'] in allowed(user,'can_use_mikajani')])
    except ValueError:raise HTTPException(503,'Kayıtlı rapor kanıtı doğrulanamadı; veri değiştirilmedi.') from None


@router.get('/inventory')
def report_inventory(user:dict=Depends(current_demo_user)):
    require_feature(user,'can_view_reports')
    rows=items_for(demo_subscriptions.store.list_items(),user,'can_view_reports')
    return dict(routers=routers_for(user,'can_view_reports'),items=[{'id':row['id']} for row in rows],is_demo=True)
