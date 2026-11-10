"""Per-item committed receipts in the existing audit table. No device or RADIUS calls."""
from datetime import datetime,date,timedelta,timezone
from zoneinfo import ZoneInfo
import hashlib,json,re
from uuid import UUID
from sqlalchemy import select,func,case
from app.core.database import SessionLocal
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as Event
from app.services.subscriber_center import SubscriberWorkspace,request_audit
from app.services.router_workspace import guard,boundary,WorkspaceError

PUBLIC_FIELDS={'customer_name','plan','status','expires_on','router_id','username','access_type','source'}

def fingerprint(command,actor):
    return hashlib.sha256(json.dumps([actor,command.model_dump(mode='json')],sort_keys=True,separators=(',',':')).encode()).hexdigest()

def public_changes(changes,key):
    return {name:change.get(key) for name,change in changes.items() if name in PUBLIC_FIELDS and isinstance(change,dict)}

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
    def prior(session,command,actor):
        prior=session.get(Event,str(command.request_id))
        if prior:
            if prior.actor_id!=actor or prior.changes.get('_management',{}).get('fingerprint')!=fingerprint(command,actor):raise WorkspaceError(409,'İstek kimliği başka bir işleme ait. Yeni önizleme oluşturun.')
            return event_receipt(prior)
    @boundary
    def change(self,command,actor):
        with self.sessions.begin() as session:
            self.check(session)
            prior=self.prior(session,command,actor)
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
            row=session.get(Account,command.item_id,with_for_update=True)
            prior=self.prior(session,command,actor)
            if prior:return prior
            if not row:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
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
                if not old or old!=command.expected_expires_on or command.days not in (30,60,90):raise WorkspaceError(409,'Bitiş tarihi bilinmiyor/değişti veya uzatma süresi geçersiz.')
                try:expected=(max(date.fromisoformat(old),today)+timedelta(days=command.days)).isoformat()
                except (ValueError,OverflowError):raise WorkspaceError(422,'Kayıtlı tarih veya uzatma aralığı geçersiz.') from None
                if value!=expected:raise WorkspaceError(409,'Türkiye gününe göre uzatma önizlemesi değişti; yeniden inceleyin.')
            old=row.fields.get(field)
            if old==value:raise WorkspaceError(422,'Yeni değer mevcut değerden farklı olmalı.')
            before=row.fields
            previous_router=row.router_id;row.fields={**row.fields,field:value}
            if field=='router_id':row.router_id=value
            row.revision+=1;stamp=datetime.now(timezone.utc).isoformat()
            previous={field:old};values={field:value}
            if field in ('plan','expires_on'):
                previous.update({key:before.get(key) for key in ('plan','expires_on')})
                values.update({key:row.fields.get(key) for key in ('plan','expires_on')})
            receipt=dict(item_id=row.id,request_id=str(command.request_id),success=True,recorded=True,operation=command.operation,actor_id=actor,router_id=row.router_id,previous_router_id=previous_router,previous=previous,values=values,occurred_at=stamp,revision=row.revision,error=None)
            self.audit(session,command,actor,row.revision,{key:{'previous':previous[key],'new':values[key]} for key in values},receipt,row.source)
            return receipt
    @staticmethod
    def audit(session,command,actor,revision,changes,receipt,source=None):
        session.add(Event(id=str(command.request_id),subscriber_id=command.item_id,actor_id=actor,revision=revision,operation=command.operation,occurred_at=receipt['occurred_at'],changes={**changes,'_source':source,'_management':{'fingerprint':fingerprint(command,actor),'receipt':receipt}}))
    @boundary
    def failed(self,command,actor,error):
        with self.sessions.begin() as session:
            self.check(session);prior=self.prior(session,command,actor)
            if prior:return prior
            row=session.get(Account,command.item_id,with_for_update=True)
            prior=self.prior(session,command,actor)
            if prior:return prior
            receipt=dict(item_id=command.item_id,request_id=str(command.request_id),success=False,recorded=True,operation=command.operation,actor_id=actor,router_id=row.router_id if row else None,previous_router_id=row.router_id if row else None,previous={},values={},occurred_at=datetime.now(timezone.utc).isoformat(),revision=row.revision if row else 0,error=error.detail)
            self.audit(session,command,actor,receipt['revision'],{},receipt,row.source if row and row.fields.get('source')==row.source else None)
            return receipt
    @boundary
    def lookup(self,command,actor):
        with self.sessions() as session:
            self.check(session);return self.prior(session,command,actor)
    def execute(self,command,actor):
        try:return self.change(command,actor)
        except WorkspaceError as failure:
            if failure.status!=503:
                try:return self.failed(command,actor,failure)
                except WorkspaceError as recording_error:
                    if recording_error.status==409:
                        try:
                            prior=self.lookup(command,actor)
                            if prior:return prior
                        except WorkspaceError:pass
            # Persistence is unavailable or request ID conflicts: never claim a saved receipt.
            return dict(item_id=command.item_id,request_id=str(command.request_id),success=False,recorded=False,operation=command.operation,actor_id=actor,router_id=None,previous_router_id=None,previous={},values={},occurred_at=datetime.now(timezone.utc).isoformat(),revision=0,error=failure.detail)
    @boundary
    def request_result(self,request_id,actor):
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
            if (receipt.get('revision')!=prior.revision or receipt.get('operation')!=prior.operation
                    or receipt.get('occurred_at')!=prior.occurred_at or type(receipt.get('success')) is not bool
                    or receipt.get('values')!=public_changes(prior.changes,'new')
                    or receipt.get('previous')!=public_changes(prior.changes,'previous')):return result
            if prior.operation=='ROUTER' and receipt['success']:
                if receipt.get('router_id')!=receipt['values'].get('router_id') or receipt.get('previous_router_id')!=receipt['previous'].get('router_id'):return result
            elif receipt.get('router_id')!=receipt.get('previous_router_id'):return result
            evidence=request_audit(prior,account,receipt.get('router_id'),account.source if account else None,receipt['success'])
            if not evidence:return result
            if account.revision==prior.revision and receipt['success'] and any(account.fields.get(key)!=value for key,value in receipt['values'].items()):return result
            return {**result,'status':'SUCCESS' if receipt['success'] else 'FAILED','response':receipt,'audit':evidence}

    @boundary
    def history(self,item_id='',operation='ALL',result='ALL',page=1,page_size=25,*,start=None,until=None,router_id='',actor_id='',query=''):
        with self.sessions() as session:
            self.check(session);clauses=[]
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
            return dict(items=[event_receipt(e) for e in rows],total=total,page=page,page_size=page_size,is_demo=True)

operations=SubscriberOperationsService()
