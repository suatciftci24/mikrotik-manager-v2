"""Persistent synthetic routers/public trust profiles. No device adapter or secret access."""
from datetime import datetime,timezone
from functools import wraps
from uuid import uuid4
from sqlalchemy import select,func
from sqlalchemy.exc import SQLAlchemyError,IntegrityError,OperationalError,InterfaceError
from app.core.database import SessionLocal
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.services.demo_subscriptions import DemoStorageUnavailable
from app.models.router_workspace import RouterWorkspaceRecord as Record,RouterWorkspaceAudit as Audit
from app.integrations.cebeci_access import verified_tls_context

class WorkspaceError(Exception):
    def __init__(self,status,detail):self.status=status;self.detail=detail

def guard(session):
    import os
    from app.core.v26_acceptance import PROFILE
    schema='v26_acceptance' if os.environ.get('V2_DEPLOYMENT_PROFILE')==PROFILE else 'v2_demo'
    PostgresDemoStore(session.get_bind(),schema=schema)._verify(session.connection())

def storage_error_detail(error):
    """Classify driver evidence, never expose SQL, parameters or server error text."""
    if isinstance(error,DemoStorageUnavailable):
        return 'Yerel çalışma alanının bağlantı profili veya sentetik depo kimliği doğrulanamadı. Migration gereksinimi belirlenmedi; veri belleğe kaydedilmedi.'
    original=getattr(error,'orig',None)
    state=getattr(original,'sqlstate',None) or getattr(original,'pgcode',None) or ''
    if state=='42501':
        return 'Yerel çalışma alanı için veritabanı erişim yetkisi yetersiz. Bağlantı rolü ve şema/tablo izinleri kontrol edilmeli; migration gereksinimi doğrulanmadı.'
    if state.startswith('28'):
        return 'Yerel çalışma alanının veritabanı kimlik doğrulaması başarısız. Bağlantı profili kontrol edilmeli; migration gereksinimi doğrulanmadı.'
    if state in ('42P01','3F000'):
        # Only our own qualified SQL identifies which migration owns the missing object.
        statement=(getattr(error,'statement',None) or '').replace('"','')
        if 'v2_subscriber_workspace.' in statement and 'v2_router_workspace.' in statement:
            return 'Yerel çalışma alanı sorgusunda şema veya tablo bulunamadı. Sorgu 007 ve 008 kapsamını birlikte kullanıyor; eksik nesne salt okunur katalog kontrolüyle belirlenmeli. Otomatik migration yapılmadı.'
        if 'v2_subscriber_workspace.' in statement:
            return 'Yerel abone çalışma alanı tablosu bulunamadı. Hedef veritabanında migration 008 ve bağımlılığı 007 salt okunur doğrulanmalı; otomatik migration yapılmadı.'
        if 'v2_router_workspace.' in statement:
            return 'Yerel router çalışma alanı tablosu bulunamadı. Hedef veritabanında V2 migration 007 salt okunur doğrulanmalı; otomatik migration yapılmadı.'
        return 'Yerel çalışma alanının sorguladığı veritabanı nesnesi bulunamadı. Bağlantı profili ve hedef şema kontrol edilmeli; migration numarası doğrulanmadı.'
    if state in ('42703','42804','42883','42601'):
        return 'Yerel çalışma alanının kod ve veritabanı şema/sürüm sözleşmesi uyuşmuyor. Kolon ve veri türleri salt okunur doğrulanmalı; migration gereksinimi belirlenmedi.'
    if state.startswith('08') or state in ('57P01','57P02','57P03') or isinstance(error,(OperationalError,InterfaceError)):
        return 'Yerel çalışma alanı veritabanı bağlantısı kurulamadı veya kesildi. Sunucu erişimi ve bağlantı profili kontrol edilmeli; migration gereksinimi doğrulanmadı.'
    return 'Yerel çalışma alanı veritabanı işlemi tamamlanamadı. Hata türü için güvenli teşhis gerekli; migration gereksinimi doğrulanmadı. Veri belleğe kaydedilmedi.'

def boundary(method):
    @wraps(method)
    def call(*args,**kwargs):
        try:return method(*args,**kwargs)
        except IntegrityError:raise WorkspaceError(409,'Kayıt başka kayıtlarla ilişkili veya aynı kimlik zaten kullanılıyor; işlem uygulanmadı.') from None
        except (SQLAlchemyError,DemoStorageUnavailable) as error:raise WorkspaceError(503,storage_error_detail(error)) from None
    return call

def public(row):
    return dict(id=row.id,kind=row.kind,revision=row.revision,fields=row.fields,is_demo=row.kind=='DEMO_ROUTER',device_connected=False,persistence='local-postgresql-workspace')

class RouterWorkspace:
    def __init__(self,sessions=SessionLocal,check=guard):self.sessions=sessions;self.check=check
    @staticmethod
    def audit(session,row,actor,action):
        session.add(Audit(id=str(uuid4()),record_id=row.id,actor_id=actor,action=action,revision=row.revision,occurred_at=datetime.now(timezone.utc).isoformat()))
    @boundary
    def list(self,kind,query='',page=1,page_size=25):
        with self.sessions() as session:
            self.check(session)
            clauses=[Record.kind==kind]
            if query:clauses.append(Record.fields['name'].as_string().ilike('%'+query.replace('!','!!').replace('%','!%').replace('_','!_')+'%',escape='!'))
            total=session.scalar(select(func.count()).select_from(Record).where(*clauses))
            rows=session.scalars(select(Record).where(*clauses).order_by(Record.id).offset((page-1)*page_size).limit(page_size)).all()
            return dict(items=[public(r) for r in rows],total=total,page=page,page_size=page_size)
    @boundary
    def detail(self,id,kind):
        with self.sessions() as session:
            self.check(session);row=session.get(Record,id)
            if not row or row.kind!=kind:raise WorkspaceError(404,'Kayıt bu çalışma alanında bulunamadı.')
            return public(row)
    @boundary
    def center_detail(self,id):
        with self.sessions() as session:
            self.check(session);row=session.get(Record,id)
            if not row or row.kind!='DEMO_ROUTER':raise WorkspaceError(404,'Sentetik router bu çalışma alanında bulunamadı.')
            events=session.scalars(select(Audit).where(Audit.record_id==id).order_by(Audit.occurred_at.desc(),Audit.id).limit(50)).all()
            return public(row),[dict(action=e.action,occurred_at=e.occurred_at,actor_id=e.actor_id,revision=e.revision) for e in events]
    @boundary
    def save(self,kind,payload,actor,id=None):
        values=payload.fields.model_dump(mode='json')
        if kind=='TRUST_PROFILE':
            try:verified_tls_context(values['ca_pem'])
            except ValueError:raise WorkspaceError(422,'Public CA geçersiz. PEM biçimindeki public CA zincirini seçin; özel anahtar kullanmayın.') from None
        prefix='demo-managed-router-' if kind=='DEMO_ROUTER' else 'trust-profile-'
        target=id or prefix+str(payload.request_id)
        with self.sessions.begin() as session:
            self.check(session);row=session.get(Record,target,with_for_update=True)
            if id and (not row or row.kind!=kind):raise WorkspaceError(404,'Kayıt bu çalışma alanında bulunamadı.')
            if not id and row:
                if row.kind==kind and row.fields==values:return public(row)
                raise WorkspaceError(409,'İstek kimliği başka bir kayda ait.')
            if payload.expected_revision!=(row.revision if row else 0):raise WorkspaceError(409,'Kayıt değişti. Güncel kaydı açıp yeniden düzenleyin.')
            if not row:row=Record(id=target,kind=kind,revision=0);session.add(row)
            row.fields=values;row.revision+=1
            self.audit(session,row,actor,'UPDATED' if id else 'CREATED')
            return public(row)
    @boundary
    def delete(self,id,kind,payload,actor):
        with self.sessions.begin() as session:
            self.check(session);row=session.get(Record,id,with_for_update=True)
            if not row or row.kind!=kind:raise WorkspaceError(404,'Kayıt bu çalışma alanında bulunamadı.')
            if row.revision!=payload.expected_revision:raise WorkspaceError(409,'Kayıt değişti; silmeden önce yenileyin.')
            row.revision+=1;self.audit(session,row,actor,'DELETED');session.delete(row)
            return {'deleted':True,'device_connected':False}

workspace=RouterWorkspace()
