"""Per-item committed receipts in the existing audit table. No device or RADIUS calls."""
from datetime import datetime,date,timedelta,timezone
from zoneinfo import ZoneInfo
import hashlib,json,re
from uuid import UUID
from sqlalchemy import select,func,case
from app.core.database import SessionLocal
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as Event
from app.services.subscriber_center import SubscriberWorkspace,request_audit,event_scope
from app.services.router_workspace import guard,boundary,WorkspaceError

PUBLIC_FIELDS={'customer_name','plan','status','expires_on','started_on','router_id','username','access_type','source','package_id','package_revision'}

def fingerprint(command,actor):
    values=command.model_dump(mode='json')
    for key in ('package_id','package_revision'):
        if key not in command.model_fields_set:values.pop(key,None)
    return hashlib.sha256(json.dumps([actor,values],sort_keys=True,separators=(',',':')).encode()).hexdigest()

def public_changes(changes,key):
    return {name:(None if change.get(key) is None else str(change[key])) for name,change in changes.items() if name in PUBLIC_FIELDS and isinstance(change,dict)}

def event_receipt(event):
    stored=event.changes.get('_management',{}).get('receipt')
    if stored:
        # History must obey the same canonical audit identity as UUID recovery.
        expected=dict(item_id=event.subscriber_id,request_id=event.id,actor_id=event.actor_id,
                      revision=event.revision,operation=event.operation,occurred_at=event.occurred_at,
                      previous=public_changes(event.changes,'previous'),values=public_changes(event.changes,'new'))
        if (stored.get('recorded') is not True or type(stored.get('success')) is not bool
                or any(stored.get(key)!=value for key,value in expected.items())
                or (stored.get('router_id')!=stored.get('previous_router_id') if event.operation!='ROUTER' or not stored['success']
                    else stored.get('router_id')!=stored['values'].get('router_id') or stored.get('previous_router_id')!=stored['previous'].get('router_id'))):
            raise WorkspaceError(409,'İşlem geçmişinin audit kanıtı uyuşmuyor; kayıt başarı sayılmadı.')
        return stored
    previous=public_changes(event.changes,'previous');values=public_changes(event.changes,'new')
    return dict(item_id=event.subscriber_id,request_id=event.id,success=True,recorded=True,operation=event.operation,actor_id=event.actor_id,
                router_id=event.changes.get('_router_id',values.get('router_id')),previous_router_id=previous.get('router_id'),previous=previous,values=values,occurred_at=event.occurred_at,revision=event.revision,error=None)

class SubscriberOperationsService:
    def __init__(self,sessions=SessionLocal,check=guard):self.sessions=sessions;self.check=check
    @staticmethod
    def prior(session,command,actor,user=None):
        prior=session.get(Event,str(command.request_id))
        if prior:
            if prior.actor_id!=actor or prior.changes.get('_management',{}).get('fingerprint')!=fingerprint(command,actor):raise WorkspaceError(409,'İstek kimliği başka bir işleme ait. Yeni önizleme oluşturun.')
            receipt=event_receipt(prior)
            if user is not None:
                from app.core.authorization import require_workspace_router
                for key in ('router_id','previous_router_id'):
                    if receipt.get(key):require_workspace_router(user,receipt[key])
            return receipt
    @boundary
    def change(self,command,actor,user=None):
        with self.sessions.begin() as session:
            self.check(session)
            if user is not None:
                row=session.get(Account,command.item_id)
                if not row:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
                SubscriberWorkspace.authorize(row,user,True)
                from app.core.authorization import require_workspace_account
                require_workspace_account(user,command.expected_router_id,row.access_type,True)
                if command.operation=='ROUTER':
                    from app.core.security import current_admin
                    current_admin(user)
            if user is None:
                prior=self.prior(session,command,actor,user=user)
                if prior:return prior
            parents={command.expected_router_id}
            if command.operation=='ROUTER':
                try:
                    value=command.value or ''
                    if not value.startswith('demo-managed-router-'):raise ValueError()
                    UUID(value.removeprefix('demo-managed-router-'))
                except ValueError:raise WorkspaceError(422,'Yalnız kalıcı sentetik router ID seçin.') from None
                parents.add(value)
            for id in sorted(parents):SubscriberWorkspace.parent(session,id)
            row=session.get(Account,command.item_id,with_for_update=True,populate_existing=True)
            if not row:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
            SubscriberWorkspace.authorize(row,user,True)
            prior=self.prior(session,command,actor,user=user)
            if prior:return prior
            if row.revision!=command.expected_revision or row.router_id!=command.expected_router_id or row.source!=command.expected_source or row.fields.get('source')!=row.source or row.fields.get('router_id')!=row.router_id:raise WorkspaceError(409,'Abone, router veya kaynak değişti. Güncel kaydı yeniden seçin.')
            field={'EDIT':'customer_name','PLAN':'plan','STATUS':'status','EXPIRE':'expires_on','EXTEND':'expires_on','ROUTER':'router_id'}[command.operation]
            value=command.value
            if command.operation in ('EDIT','PLAN'):
                value=(value or '').strip();limit=160 if command.operation=='EDIT' else 120
                if not (2 if command.operation=='EDIT' else 1)<=len(value)<=limit or not value.isprintable():raise WorkspaceError(422,'Ad veya paket/profil alanı geçersiz.')
            elif command.operation=='STATUS':
                if value not in ('ACTIVE','PAUSED'):raise WorkspaceError(422,'Hesap durumu Aktif veya Pasif olmalı.')
            elif command.operation=='EXPIRE' and value is not None:
                try:
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value) or date.fromisoformat(value).isoformat()!=value:raise ValueError()
                except ValueError:raise WorkspaceError(422,'Bitiş tarihi YYYY-MM-DD biçiminde olmalı.') from None
            elif command.operation=='EXTEND':
                old=row.fields.get('expires_on');today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
                if not old or old!=command.expected_expires_on or command.days is None:raise WorkspaceError(409,'Bitiş tarihi bilinmiyor/değişti veya uzatma süresi eksik.')
                try:
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',old):raise ValueError()
                    expected=(max(date.fromisoformat(old),today)+timedelta(days=command.days)).isoformat()
                except (ValueError,OverflowError):raise WorkspaceError(422,'Kayıtlı tarih veya uzatma aralığı geçersiz.') from None
                if value!=expected:raise WorkspaceError(409,'Türkiye gününe göre uzatma önizlemesi değişti; yeniden inceleyin.')
            if field=='expires_on' and value and row.fields.get('started_on') and value<row.fields['started_on']:raise WorkspaceError(422,'Bitiş tarihi başlangıçtan önce olamaz.')
            package_values={}
            if field=='plan':
                if command.package_id:
                    from app.services.packages import binding
                    package_values=binding(session,command.package_id,command.package_revision)
                    value=package_values['plan']
                else:package_values=dict(package_id=None,package_revision=None,package_snapshot=None)
            old=row.fields.get(field)
            if old==value and all(row.fields.get(key)==val for key,val in package_values.items()):raise WorkspaceError(422,'Yeni değer mevcut değerden farklı olmalı.')
            before=row.fields
            previous_router=row.router_id;row.fields={**row.fields,**package_values,field:value}
            if field=='router_id':row.router_id=value
            row.revision+=1;stamp=datetime.now(timezone.utc).isoformat()
            previous={field:old};values={field:value}
            if field in ('plan','expires_on'):
                previous.update({key:before.get(key) for key in ('plan','expires_on')})
                values.update({key:row.fields.get(key) for key in ('plan','expires_on')})
            if field=='plan':
                for key in ('package_id','package_revision'):
                    previous[key]=None if before.get(key) is None else str(before[key])
                    values[key]=None if row.fields.get(key) is None else str(row.fields[key])
            receipt=dict(item_id=row.id,request_id=str(command.request_id),success=True,recorded=True,operation=command.operation,actor_id=actor,router_id=row.router_id,previous_router_id=previous_router,previous=previous,values=values,occurred_at=stamp,revision=row.revision,error=None)
            changes={key:{'previous':previous[key],'new':values[key]} for key in values}
            if field=='plan':changes['_package_snapshot']={'previous':before.get('package_snapshot'),'new':row.fields.get('package_snapshot')}
            self.audit(session,command,actor,row.revision,changes,receipt,row.source)
            return receipt
    @staticmethod
    def audit(session,command,actor,revision,changes,receipt,source=None):
        session.add(Event(id=str(command.request_id),subscriber_id=command.item_id,actor_id=actor,revision=revision,operation=command.operation,occurred_at=receipt['occurred_at'],changes={**changes,'_source':source,'_management':{'fingerprint':fingerprint(command,actor),'receipt':receipt}}))
    @boundary
    def failed(self,command,actor,error,user=None):
        with self.sessions.begin() as session:
            self.check(session)
            if user is None:
                prior=self.prior(session,command,actor,user=user)
                if prior:return prior
            row=session.get(Account,command.item_id,with_for_update=True)
            if user is not None:
                if row is None:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
                SubscriberWorkspace.authorize(row,user,True)
            prior=self.prior(session,command,actor,user=user)
            if prior:return prior
            receipt=dict(item_id=command.item_id,request_id=str(command.request_id),success=False,recorded=True,operation=command.operation,actor_id=actor,router_id=row.router_id if row else None,previous_router_id=row.router_id if row else None,previous={},values={},occurred_at=datetime.now(timezone.utc).isoformat(),revision=row.revision if row else 0,error=error.detail)
            self.audit(session,command,actor,receipt['revision'],{},receipt,row.source if row and row.fields.get('source')==row.source else None)
            return receipt
    @boundary
    def lookup(self,command,actor,user=None):
        with self.sessions() as session:
            self.check(session)
            if user is not None:
                row=session.get(Account,command.item_id)
                if row is None:return None
                SubscriberWorkspace.authorize(row,user,True)
            return self.prior(session,command,actor,user=user)
    def execute(self,command,actor,user=None):
        try:return self.change(command,actor,user=user)
        except WorkspaceError as failure:
            if failure.status!=503:
                try:return self.failed(command,actor,failure,user=user)
                except WorkspaceError as recording_error:
                    if recording_error.status==409:
                        try:
                            prior=self.lookup(command,actor,user=user)
                            if prior:return prior
                        except WorkspaceError:pass
            # Persistence is unavailable or request ID conflicts: never claim a saved receipt.
            return dict(item_id=command.item_id,request_id=str(command.request_id),success=False,recorded=False,operation=command.operation,actor_id=actor,router_id=None,previous_router_id=None,previous={},values={},occurred_at=datetime.now(timezone.utc).isoformat(),revision=0,error=failure.detail)
    @boundary
    def request_result(self,request_id,actor,user=None):
        with self.sessions() as session:
            if session.bind.dialect.name=='postgresql':
                session.connection(execution_options={'isolation_level':'REPEATABLE READ','postgresql_readonly':True})
            self.check(session)
            result={'request_id':str(request_id),'status':'UNKNOWN','response':None}
            prior=session.get(Event,str(request_id))
            if not prior or prior.actor_id!=actor:return result
            receipt=prior.changes.get('_management',{}).get('receipt')
            if not receipt or receipt.get('recorded') is not True or receipt.get('request_id')!=str(request_id) or receipt.get('item_id')!=prior.subscriber_id or receipt.get('actor_id')!=actor:return result
            account=session.get(Account,prior.subscriber_id)
            if user is not None and account is not None:
                SubscriberWorkspace.authorize(account,user)
                from app.core.authorization import require_workspace_router
                for key in ('router_id','previous_router_id'):
                    if receipt.get(key):require_workspace_router(user,receipt[key])
            if (receipt.get('revision')!=prior.revision or receipt.get('operation')!=prior.operation
                    or receipt.get('occurred_at')!=prior.occurred_at or type(receipt.get('success')) is not bool
                    or receipt.get('values')!=public_changes(prior.changes,'new')
                    or receipt.get('previous')!=public_changes(prior.changes,'previous')):return result
            if prior.operation=='ROUTER' and receipt['success']:
                if receipt.get('router_id')!=receipt['values'].get('router_id') or receipt.get('previous_router_id')!=receipt['previous'].get('router_id'):return result
            elif receipt.get('router_id')!=receipt.get('previous_router_id'):return result
            evidence=request_audit(prior,account,receipt.get('router_id'),account.source if account else None,receipt['success'])
            if not evidence:return result
            if account.revision==prior.revision and receipt['success'] and any((None if account.fields.get(key) is None else str(account.fields[key]))!=value for key,value in receipt['values'].items()):return result
            return {**result,'status':'SUCCESS' if receipt['success'] else 'FAILED','response':receipt,'audit':evidence}

    @boundary
    def history(self,item_id='',operation='ALL',result='ALL',page=1,page_size=25,*,start=None,until=None,router_id='',actor_id='',query='',user=None):
        with self.sessions() as session:
            self.check(session);clauses=[]
            if user is not None:
                from app.core.authorization import workspace_scope
                ids=workspace_scope(user)
                if ids is not None:clauses.extend([Account.router_id.in_(ids),*event_scope(ids)])
            if start:clauses.append(Event.occurred_at>=start)
            if until:clauses.append(Event.occurred_at<until)
            if item_id:clauses.append(Event.subscriber_id==item_id)
            if router_id:clauses.append(Account.router_id==router_id)
            if actor_id:clauses.append(Event.actor_id==actor_id)
            if operation!='ALL':clauses.append(Event.operation==operation)
            if query:
                pattern='%'+query+'%'
                clauses.append((Event.id.ilike(pattern))|(Event.actor_id.ilike(pattern))|(Event.subscriber_id.ilike(pattern))|(Account.fields['customer_name'].as_string().ilike(pattern))|(Account.fields['username'].as_string().ilike(pattern)))
            if result!='ALL':
                # CREATE/UPDATE/RENEWAL audits commit atomically and have no management receipt.
                # Match event_receipt instead of classifying those successes as unknown.
                success=case((Event.operation.in_(('CREATE','UPDATE','RENEWAL')),True),
                             else_=Event.changes['_management']['receipt']['success'].as_boolean())
                clauses.append(success.is_(False) if result=='FAILED' else success.is_(True) if result=='SUCCESS' else success.is_(None))
            statement=select(Event).join(Account,Account.id==Event.subscriber_id).where(*clauses)
            total=session.scalar(select(func.count()).select_from(Event).join(Account,Account.id==Event.subscriber_id).where(*clauses))
            rows=session.scalars(statement.order_by(Event.occurred_at.desc(),Event.id).offset((page-1)*page_size).limit(page_size)).all()
            from app.services.subscriber_center import event_source
            return dict(items=[{**event_receipt(e),'source':event_source(e)} for e in rows],total=total,page=page,page_size=page_size,is_demo=True)

operations=SubscriberOperationsService()
