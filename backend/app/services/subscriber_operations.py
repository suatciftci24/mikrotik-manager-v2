"""Per-item committed receipts in the existing audit table. No device or RADIUS calls."""
from datetime import datetime,date,timedelta,timezone
from zoneinfo import ZoneInfo
import hashlib,json,re
from uuid import UUID
from sqlalchemy import select,func
from app.core.database import SessionLocal
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as Event
from app.services.subscriber_center import SubscriberWorkspace
from app.services.router_workspace import guard,boundary,WorkspaceError

PUBLIC_FIELDS={'customer_name','plan','status','expires_on','router_id','username','access_type','source'}

def fingerprint(command,actor):
    return hashlib.sha256(json.dumps([actor,command.model_dump(mode='json')],sort_keys=True,separators=(',',':')).encode()).hexdigest()

def public_changes(changes,key):
    return {name:change.get(key) for name,change in changes.items() if name in PUBLIC_FIELDS and isinstance(change,dict)}

def event_receipt(event):
    stored=event.changes.get('_management',{}).get('receipt')
    if stored:return stored
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
                expected=(max(date.fromisoformat(old),today)+timedelta(days=command.days)).isoformat()
                if value!=expected:raise WorkspaceError(409,'Türkiye gününe göre uzatma önizlemesi değişti; yeniden inceleyin.')
            old=row.fields.get(field)
            if old==value:raise WorkspaceError(422,'Yeni değer mevcut değerden farklı olmalı.')
            previous_router=row.router_id;row.fields={**row.fields,field:value}
            if field=='router_id':row.router_id=value
            row.revision+=1;stamp=datetime.now(timezone.utc).isoformat()
            receipt=dict(item_id=row.id,request_id=str(command.request_id),success=True,recorded=True,operation=command.operation,actor_id=actor,router_id=row.router_id,previous_router_id=previous_router,previous={field:old},values={field:value},occurred_at=stamp,revision=row.revision,error=None)
            self.audit(session,command,actor,row.revision,{field:{'previous':old,'new':value}},receipt)
            return receipt
    @staticmethod
    def audit(session,command,actor,revision,changes,receipt):
        session.add(Event(id=str(command.request_id),subscriber_id=command.item_id,actor_id=actor,revision=revision,operation=command.operation,occurred_at=receipt['occurred_at'],changes={**changes,'_management':{'fingerprint':fingerprint(command,actor),'receipt':receipt}}))
    @boundary
    def failed(self,command,actor,error):
        with self.sessions.begin() as session:
            self.check(session);prior=self.prior(session,command,actor)
            if prior:return prior
            row=session.get(Account,command.item_id,with_for_update=True)
            prior=self.prior(session,command,actor)
            if prior:return prior
            receipt=dict(item_id=command.item_id,request_id=str(command.request_id),success=False,recorded=True,operation=command.operation,actor_id=actor,router_id=row.router_id if row else None,previous_router_id=row.router_id if row else None,previous={},values={},occurred_at=datetime.now(timezone.utc).isoformat(),revision=row.revision if row else 0,error=error.detail)
            self.audit(session,command,actor,receipt['revision'],{},receipt)
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
    def history(self,item_id='',operation='ALL',result='ALL',page=1,page_size=25):
        with self.sessions() as session:
            self.check(session);clauses=[]
            if item_id:clauses.append(Event.subscriber_id==item_id)
            if operation!='ALL':clauses.append(Event.operation==operation)
            if result!='ALL':
                success=Event.changes['_management']['receipt']['success'].as_boolean()
                clauses.append(success.is_(False) if result=='FAILED' else (success.is_(True)|success.is_(None)))
            total=session.scalar(select(func.count()).select_from(Event).where(*clauses))
            rows=session.scalars(select(Event).where(*clauses).order_by(Event.occurred_at.desc(),Event.id).offset((page-1)*page_size).limit(page_size)).all()
            return dict(items=[event_receipt(e) for e in rows],total=total,page=page,page_size=page_size,is_demo=True)

operations=SubscriberOperationsService()
