from app.core.authorization import routers_for,items_for,require_feature,require_router,allowed,router_id as item_router_id,is_admin
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import current_demo_user,current_admin
from app.services import demo_subscriptions
from app.services.demo_data import ROUTERS
from app.services.operation_reports import report_range, project_report

router=APIRouter(prefix='/reports',tags=['read-only-reports'],dependencies=[Depends(current_demo_user)])


@router.get('/audit-center')
def audit_center(start:str,end:str,source:Literal['SUBSCRIBER','WAN','USER','WORKSPACE']='SUBSCRIBER',
                 router_id:str='',actor_id:str='',operation:str='',result:Literal['ALL','SUCCESS','FAILED','UNKNOWN']='ALL',
                 query:str=Query('',max_length=120),page:int=Query(1,ge=1,le=10000),page_size:int=Query(25,ge=1,le=50),
                 user:dict=Depends(current_demo_user)):
    """One filtered read surface over existing, explicitly scoped audit sources."""
    try:bounds=report_range(start,end,datetime.now(timezone.utc))
    except ValueError as error:raise HTTPException(422,str(error)) from None
    require_feature(user,'can_view_reports')
    scope=routers_for(user,'can_view_reports')
    if router_id:
        require_router(user,router_id,'can_view_reports')
        if router_id not in {r['id'] for r in scope}:raise HTTPException(403,'Rapor yetkisi gerekli')
    selected=next((r for r in scope if r['id']==router_id),None)
    if router_id and selected is None:raise HTTPException(422,'Bilinmeyen sentetik router.')
    admin_scope=is_admin(user) and user.get('can_manage_users') is True
    if source in ('USER','WORKSPACE'):current_admin(user)
    if source=='WAN' and actor_id:raise HTTPException(422,'WAN olaylarında aktör kimliği kaydedilmez; aktör filtresini kaldırın.')
    rows=[];total=0;available=True
    if source=='USER':
        if router_id:raise HTTPException(422,'Kullanıcı denetim kayıtlarında router ilişkisi yoktur; router filtresini kaldırın.')
        from app.services import identity
        stored_result={'SUCCESS':'SUCCESS','FAILED':'REJECTED','UNKNOWN':'UNKNOWN','ALL':''}[result]
        resultset=identity.audit_users(page,page_size,start=bounds[0].astimezone(timezone.utc),until=bounds[1].astimezone(timezone.utc),actor_id=actor_id,operation=operation,result=stored_result,query=query)
        available=resultset.get('available') is True
        rows=[dict(id=str(row['id']),audit_id=str(row['id']),occurred_at=row['occurred_at'],actor_id=row['actor_id'],target_id=row['target_id'],
                   router_id=None,subscriber_id=None,operation=row['operation'],result='FAILED' if row['result']=='REJECTED' else row['result'] if row['result'] in ('SUCCESS','UNKNOWN') else 'UNKNOWN',
                   source='USER_AUDIT',details={'previous':_safe_user_values(row.get('previous_values')),'next':_safe_user_values(row.get('new_values'))}) for row in resultset['items']]
        total=resultset['total']
    elif source=='WORKSPACE':
        from app.services.subscriber_operations import operations
        from app.services.subscriber_center import workspace
        raw=operations.history(operation=operation or 'ALL',result=result,page=page,page_size=page_size,
            start=bounds[0].astimezone(timezone.utc).isoformat(),until=bounds[1].astimezone(timezone.utc).isoformat(),router_id=router_id,actor_id=actor_id,query=query)
        # Resolve only public display fields from the existing ADMIN-only workspace list.
        listed=workspace.list(query, 'ALL','ALL',router_id,1,100)
        accounts={item['id']:item for item in listed['items']}
        for receipt in raw['items']:
            item=accounts.get(receipt['item_id']);status='SUCCESS' if receipt.get('success') is True and receipt.get('recorded') is True else 'FAILED' if receipt.get('success') is False and receipt.get('recorded') is True else 'UNKNOWN'
            rows.append(dict(id=receipt['request_id'],audit_id=receipt['request_id'],occurred_at=receipt['occurred_at'],actor_id=receipt['actor_id'],target_id=receipt['item_id'],
                subscriber_id=receipt['item_id'],router_id=receipt.get('router_id'),operation=receipt['operation'],result=status,source='SUBSCRIBER_WORKSPACE',
                details={'subscriber':item['customer_name'] if item else None,'username':item['username'] if item else None,'access_type':item['access_type'] if item else None,
                         'changes':{'previous':_safe_changes(receipt.get('previous')),'next':_safe_changes(receipt.get('values'))}}))
        total=raw['total']
    elif source=='WAN':
        source_rows=router_event_records(items_for(demo_subscriptions.store.list_items(),user,'can_view_reports'))
        available=source_rows.available
        filtered=[]
        for event in source_rows.items:
            stamp=datetime.fromisoformat(event.occurred_at.replace('Z','+00:00')) if event.occurred_at else None
            text=' '.join(str(value or '') for value in (event.id,event.router_id,event.kind,event.previous_wan,event.new_wan))
            status='UNKNOWN'  # WAN lifecycle state is not a management-operation result.
            if not stamp or not (bounds[0]<=stamp<bounds[1]) or router_id and event.router_id!=router_id:continue
            if operation and event.kind!=operation or result!='ALL' and status!=result or query.casefold() not in text.casefold():continue
            filtered.append(dict(id=event.id,audit_id=None,occurred_at=event.occurred_at,actor_id=None,target_id=event.router_id,subscriber_id=None,
                router_id=event.router_id,operation=event.kind,result=status,source='ROUTER_WAN',details={'previous_wan':event.previous_wan,'new_wan':event.new_wan}))
        filtered.sort(key=lambda row:(row['occurred_at'],row['id']),reverse=True);total=len(filtered);rows=filtered[(page-1)*page_size:page*page_size]
        available=available and (result=='ALL' or result=='UNKNOWN')
    else:
        from app.services.demo_subscriptions import store
        scope_ids={r['id'] for r in scope}
        if result in ('FAILED','UNKNOWN'):
            # The legacy audit table records applied changes only; it has no evidence for these outcomes.
            available=False
        else:
            items,audits,total,_groups=store.report_records(*bounds,router_id,selected['name'] if selected else '', '',operation,page_size,(page-1)*page_size,scope,actor_id=actor_id,query=query)
            filtered=[]
            for event in audits:
                stamp=datetime.fromisoformat(event['occurred_at'].replace('Z','+00:00'))
                if event.get('router_id') and event['router_id'] not in scope_ids:continue
                filtered.append(dict(id=event.get('id') or event.get('request_id'),audit_id=event.get('request_id'),occurred_at=stamp.isoformat(),actor_id=event.get('actor_id'),
                    target_id=event['subscriber_id'],subscriber_id=event['subscriber_id'],router_id=event.get('router_id'),operation=event.get('operation'),result='SUCCESS',source='LEGACY_SUBSCRIBER_AUDIT',
                    details={'subscriber':event.get('customer_name'),'username':event.get('username'),'router_name':event.get('router_name'),'access_type':event.get('access_type'),
                             'changes':{'previous':_safe_changes(event.get('previous_values')),'next':_safe_changes(event.get('new_values'))}}))
            rows=filtered
    return dict(items=rows,total=total,page=page,page_size=page_size,source=source,source_available=available,
        sources={'legacy_subscriber_audit':{'queried':source=='SUBSCRIBER','available':available if source=='SUBSCRIBER' else None,'result_coverage':'SUCCESS_ONLY'},
                 'persistent_subscriber_audit':{'queried':source=='WORKSPACE','available':admin_scope if source=='WORKSPACE' else None,'result_coverage':'RECEIPT_VERIFIED'},
                 'user_audit':{'queried':source=='USER','available':available if source=='USER' else None,'result_coverage':'RECORDED_RESULT'},
                 'router_wan':{'queried':source=='WAN','available':available if source=='WAN' else None,'result_coverage':'RECORDED_STATE'}},
        routers=scope,read_at=datetime.now(timezone.utc).isoformat(),is_demo=True,read_only=True)


def _safe_user_values(value):
    if not isinstance(value,dict):return None
    # Do not expose arbitrary audit JSON (which could contain future secret fields).
    allowed=('role','role_code','active','permissions','revision')
    safe={key:value[key] for key in allowed if key in value}
    if 'email' in value:safe['email']='[MASKED]'
    return safe or None


def _safe_changes(value):
    if not isinstance(value,dict):return None
    public={'customer_name','username','plan','status','expires_on','router_id','router_name','source','access_type'}
    return {key:entry for key,entry in value.items() if key in public and (entry is None or isinstance(entry,(str,int,float,bool)))} or None


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
