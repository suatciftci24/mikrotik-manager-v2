"""Synthetic workspace persistence and read-only legacy projection, no provisioning IO."""
from datetime import datetime,timezone
from sqlalchemy import select,func,or_
from app.core.database import SessionLocal
from app.services.router_workspace import guard,boundary,WorkspaceError
from app.models.router_workspace import RouterWorkspaceRecord as Router
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as Event
from app.schemas.subscriber_center import CenterSubscriber,SubscriberCenterData


def account_view(account,router):
    return CenterSubscriber(id=account.id,**account.fields,revision=account.revision,router_name=router.fields['name'],router_source='PERSISTENT_DEMO')

class SubscriberWorkspace:
    def __init__(self,sessions=SessionLocal,check=guard):self.sessions=sessions;self.check=check
    @staticmethod
    def parent(session,id):
        router=session.get(Router,id,with_for_update=True)
        if not router or router.kind!='DEMO_ROUTER':raise WorkspaceError(409,'Yalnız kalıcı sentetik router ID seçilebilir; gerçek cihaz ve sertifika profili kullanılamaz.')
        return router
    @boundary
    def list(self,query='',access_type='ALL',status='ALL',router_id='',page=1,page_size=25):
        with self.sessions() as session:
            self.check(session);clauses=[Router.kind=='DEMO_ROUTER']
            if query:
                term='%'+query.replace('!','!!').replace('%','!%').replace('_','!_')+'%'
                clauses.append(or_(Account.username_key.ilike(term,escape='!'),Account.fields['customer_name'].as_string().ilike(term,escape='!')))
            if access_type!='ALL':clauses.append(Account.access_type==access_type)
            if status!='ALL':clauses.append(Account.fields['status'].as_string()==status)
            if router_id:clauses.append(Account.router_id==router_id)
            base=select(Account,Router).join(Router,Account.router_id==Router.id).where(*clauses)
            total=session.scalar(select(func.count()).select_from(base.subquery()))
            rows=session.execute(base.order_by(Account.username_key,Account.id).offset((page-1)*page_size).limit(page_size)).all()
            return dict(items=[account_view(a,r) for a,r in rows],total=total,page=page,page_size=page_size,is_demo=True)
    @boundary
    def detail(self,id):
        with self.sessions() as session:
            self.check(session);account=session.get(Account,id)
            if not account:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
            router=session.get(Router,account.router_id)
            if not router or router.kind!='DEMO_ROUTER':raise WorkspaceError(409,'Sentetik router bağı doğrulanamadı.')
            events=session.scalars(select(Event).where(Event.subscriber_id==id).order_by(Event.revision.desc()).limit(50)).all()
            return SubscriberCenterData(item=account_view(account,router),source='PERSISTENT_WORKSPACE',persistence='local-postgresql-workspace',history=[dict(operation=e.operation,occurred_at=e.occurred_at,actor_id=e.actor_id,revision=e.revision) for e in events])
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
    @staticmethod
    def audit(session,row,actor,before,request_id):
        changes={key:{'previous':before.get(key),'new':value} for key,value in row.fields.items() if before.get(key)!=value}
        session.add(Event(id=request_id,subscriber_id=row.id,actor_id=actor,revision=row.revision,operation='UPDATE' if before else 'CREATE',occurred_at=datetime.now(timezone.utc).isoformat(),changes=changes))

workspace=SubscriberWorkspace()

def legacy_center(detail):
    item=detail['item'];router_id=item.get('router_id')
    from app.services.demo_data import ROUTERS
    router=next((r for r in ROUTERS if r['id']==router_id),None)
    # No name-based join, or transformation of last_seen into a connection assertion.
    return SubscriberCenterData(item=CenterSubscriber(id=item['id'],customer_name=item['customer_name'],username=item['username'],router_id=router['id'] if router else None,router_name=router['name'] if router else None,router_source='STATIC_DEMO' if router else 'UNKNOWN',
        access_type=item.get('access_type') if item.get('access_type') in ('PPPOE','HOTSPOT') else None,source=item.get('source') if item.get('source') in ('LOCAL','RADIUS') else None,plan=item['plan'],status=item['status'],expires_on=item.get('expires_on'),revision=item.get('revision',0),
        ip_address=item.get('ip_address') if item.get('ip_address') not in ('','Veri yok','Bilinmiyor') else None,last_seen_at=item.get('last_seen')),
        source='LEGACY_DEMO',persistence=detail.get('persistence','process-memory'),history=[dict(operation=e.get('operation','UNKNOWN'),occurred_at=e['occurred_at'],actor_id=e['actor_id']) for e in detail.get('history',[])[:50]])
