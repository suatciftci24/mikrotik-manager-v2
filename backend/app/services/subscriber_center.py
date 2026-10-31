"""Synthetic workspace persistence and read-only legacy projection, no provisioning IO."""
from datetime import datetime,timezone,date,timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select,func,or_
from app.core.database import SessionLocal
from app.services.router_workspace import guard,boundary,WorkspaceError
from app.models.router_workspace import RouterWorkspaceRecord as Router
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as Event
from app.schemas.subscriber_center import CenterSubscriber,SubscriberCenterData


def account_view(account,router):
    return CenterSubscriber(id=account.id,**account.fields,revision=account.revision,router_name=router.fields['name'] if router else None,router_model=router.fields.get('model') if router else None,router_missing=router is None,router_source='PERSISTENT_DEMO' if router else 'UNKNOWN')

class SubscriberWorkspace:
    def __init__(self,sessions=SessionLocal,check=guard):self.sessions=sessions;self.check=check
    @staticmethod
    def parent(session,id):
        router=session.get(Router,id,with_for_update=True)
        if not router or router.kind!='DEMO_ROUTER':raise WorkspaceError(409,'Yalnız kalıcı sentetik router ID seçilebilir; gerçek cihaz ve sertifika profili kullanılamaz.')
        return router
    @boundary
    def list(self,query='',access_type='ALL',status='ALL',router_id='',page=1,page_size=25,require_parent=False):
        with self.sessions() as session:
            self.check(session)
            if require_parent:
                parent=session.get(Router,router_id)
                if not parent or parent.kind!='DEMO_ROUTER':raise WorkspaceError(404,'Sentetik router kaydı bulunamadı.')
            clauses=[or_(Router.kind=='DEMO_ROUTER',Router.id.is_(None))]
            if query:
                term='%'+query.replace('!','!!').replace('%','!%').replace('_','!_')+'%'
                clauses.append(or_(Account.username_key.ilike(term,escape='!'),Account.fields['customer_name'].as_string().ilike(term,escape='!')))
            if access_type!='ALL':clauses.append(Account.access_type==access_type)
            if status!='ALL':clauses.append(Account.fields['status'].as_string()==status)
            if router_id:clauses.append(Account.router_id==router_id)
            base=select(Account,Router).outerjoin(Router,Account.router_id==Router.id).where(*clauses)
            total=session.scalar(select(func.count()).select_from(base.subquery()))
            rows=session.execute(base.order_by(Account.username_key,Account.id).offset((page-1)*page_size).limit(page_size)).all()
            return dict(items=[account_view(a,r) for a,r in rows],total=total,page=page,page_size=page_size,is_demo=True)
    @boundary
    def detail(self,id):
        with self.sessions() as session:
            self.check(session);account=session.get(Account,id)
            if not account:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
            router=session.get(Router,account.router_id)
            if router and router.kind!='DEMO_ROUTER':router=None
            events=session.scalars(select(Event).where(Event.subscriber_id==id).order_by(Event.occurred_at.desc(),Event.id).limit(50)).all()
            return SubscriberCenterData(item=account_view(account,router),source='PERSISTENT_WORKSPACE',persistence='local-postgresql-workspace',history=[center_event(e) for e in events])
    @boundary
    def save(self,command,actor,id=None):
        values=command.fields.model_dump(mode='json');target=id or 'demo-managed-sub-'+str(command.request_id)
        with self.sessions.begin() as session:
            self.check(session);router=self.parent(session,values['router_id']);row=session.get(Account,target,with_for_update=True)
            prior=session.get(Event,str(command.request_id))
            if prior:
                if prior.subscriber_id==target and prior.actor_id==actor and row and row.fields==values and row.revision==prior.revision:return account_view(row,router)
                raise WorkspaceError(409,'İstek kimliği başka bir işleme veya eski revizyona ait.')
            if id and not row:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
            if row and not id:
                if row.fields==values:return account_view(row,router)
                raise WorkspaceError(409,'İstek kimliği başka kayda ait.')
            if command.expected_revision!=(row.revision if row else 0):raise WorkspaceError(409,'Abone değişti. Güncel detayı açın.')
            if row and any(row.fields[key]!=values[key] for key in ('router_id','access_type','source','username')):raise WorkspaceError(409,'Router ID, kullanıcı adı, erişim türü ve yetkili kaynak düzenleme ile değiştirilemez.')
            duplicate=session.scalar(select(Account.id).where(Account.username_key==values['username'].casefold(),Account.id!=target))
            if duplicate:raise WorkspaceError(409,'Bu sentetik kullanıcı adı zaten kullanılıyor; kaynak ve tür ayrı bir hesap kopyası oluşturmaz.')
            before=row.fields if row else {}
            if not row:row=Account(id=target,router_id=values['router_id'],username_key=values['username'].casefold(),access_type=values['access_type'],source=values['source'],revision=0);session.add(row)
            row.fields=values;row.revision+=1
            self.audit(session,row,actor,before,str(command.request_id))
            return account_view(row,router)
    @boundary
    def renew(self,id,command,actor):
        with self.sessions.begin() as session:
            self.check(session);row=session.get(Account,id,with_for_update=True)
            if not row:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
            router=session.get(Router,row.router_id)
            if not router or router.kind!='DEMO_ROUTER':raise WorkspaceError(409,'Sentetik router bağı doğrulanamadı.')
            prior=session.get(Event,str(command.request_id))
            old=command.expected_expires_on.isoformat() if command.expected_expires_on else None
            new=command.expires_on.isoformat()
            if prior:
                if prior.subscriber_id==id and prior.actor_id==actor and prior.operation=='RENEWAL' and prior.revision==row.revision and prior.changes.get('expires_on')=={'previous':old,'new':new} and prior.changes.get('_renewal')=={'days':command.days,'expected_source':command.expected_source,'expected_revision':command.expected_revision} and row.fields['expires_on']==new:return account_view(row,router)
                raise WorkspaceError(409,'Uzatma isteği başka işleme veya eski revizyona ait.')
            if row.revision!=command.expected_revision or row.source!=command.expected_source or row.fields['expires_on']!=old:raise WorkspaceError(409,'Abone veya bitiş tarihi değişti. Güncel kaydı yeniden inceleyin.')
            today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
            if command.days and (old is None or max(date.fromisoformat(old),today)+timedelta(days=command.days)!=command.expires_on):raise WorkspaceError(409,'Uzatma önizlemesi değişti veya eski tarih bilinmiyor; yeniden inceleyin.')
            if command.expires_on<today or (old is not None and new<=old):raise WorkspaceError(422,'Uzatma tarihi Türkiye bugününden önce olamaz ve mevcut bitişten ileri olmalı.')
            before=row.fields;row.fields={**row.fields,'expires_on':new};row.revision+=1
            self.audit(session,row,actor,before,str(command.request_id),'RENEWAL',{'days':command.days,'expected_source':command.expected_source,'expected_revision':command.expected_revision})
            return account_view(row,router)
    @staticmethod
    def audit(session,row,actor,before,request_id,operation=None,renewal=None):
        changes={key:{'previous':before.get(key),'new':value} for key,value in row.fields.items() if before.get(key)!=value}
        changes['_router_id']=row.router_id
        if renewal is not None:changes['_renewal']=renewal
        session.add(Event(id=request_id,subscriber_id=row.id,actor_id=actor,revision=row.revision,operation=operation or ('UPDATE' if before else 'CREATE'),occurred_at=datetime.now(timezone.utc).isoformat(),changes=changes))

workspace=SubscriberWorkspace()

def legacy_center(detail):
    item=detail['item'];router_id=item.get('router_id')
    from app.services.demo_data import ROUTERS
    router=next((r for r in ROUTERS if r['id']==router_id),None)
    # No name-based join, or transformation of last_seen into a connection assertion.
    return SubscriberCenterData(item=CenterSubscriber(id=item['id'],customer_name=item['customer_name'],username=item['username'],router_id=router_id,router_name=router['name'] if router else None,router_model=router.get('model') if router else None,router_missing=bool(router_id and not router),router_source='STATIC_DEMO' if router else 'UNKNOWN',
        access_type=item.get('access_type') if item.get('access_type') in ('PPPOE','HOTSPOT') else None,source=item.get('source') if item.get('source') in ('LOCAL','RADIUS') else None,plan=item['plan'],status=item['status'],expires_on=item.get('expires_on'),revision=item.get('revision',0),
        ip_address=item.get('ip_address') if item.get('ip_address') not in ('','Veri yok','Bilinmiyor') else None,last_seen_at=item.get('last_seen')),
        source='LEGACY_DEMO',persistence=detail.get('persistence','process-memory'),history=[legacy_event(e) for e in detail.get('history',[])[:50]])

def legacy_event(event):
    previous=event.get('previous_values',{});values=event.get('new_values',{})
    has_date='expires_on' in values or 'expires_on' in event
    old=previous.get('expires_on',event.get('previous_expires_on'))
    new=values.get('expires_on',event.get('expires_on'))
    return dict(operation=event.get('operation','UNKNOWN'),occurred_at=event['occurred_at'],actor_id=event['actor_id'],previous_expires_on=old,expires_on=new,date_changed=has_date and old!=new,result='APPLIED')

def center_event(event):
    from app.services.subscriber_operations import event_receipt
    receipt=event_receipt(event)
    return dict(operation=event.operation,occurred_at=event.occurred_at,actor_id=event.actor_id,revision=event.revision,subscriber_id=event.subscriber_id,router_id=receipt['router_id'],previous_values=receipt['previous'],new_values=receipt['values'],result='APPLIED' if receipt['success'] else 'FAILED',error=receipt['error'],previous_expires_on=event.changes.get('expires_on',{}).get('previous'),expires_on=event.changes.get('expires_on',{}).get('new'),date_changed='expires_on' in event.changes and event.changes['expires_on'].get('previous')!=event.changes['expires_on'].get('new'))
