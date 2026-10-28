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
               page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=50)):
    try:
        bounds=report_range(start,end,datetime.now(timezone.utc))
    except ValueError as error:raise HTTPException(422,str(error)) from None
    selected=next((r for r in ROUTERS if r['id']==router_id),None)
    if router_id and selected is None:raise HTTPException(422,'Bilinmeyen sentetik router.')
    items,audits,total,groups=demo_subscriptions.store.report_records(*bounds,router_id,selected['name'] if selected else '',subscriber_id,operation,page_size,(page-1)*page_size)
    # Subscriber scope belongs only to the audit view; other categories remain router/date scoped.
    try:return project_report(items,ROUTERS,audits,total,groups,bounds,category,router_id,priority,state,page,page_size)
    except ValueError:raise HTTPException(503,'Kayıtlı rapor kanıtı doğrulanamadı; veri değiştirilmedi.') from None
