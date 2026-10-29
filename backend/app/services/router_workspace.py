"""Persistent synthetic routers/public trust profiles. No device adapter or secret access."""
from datetime import datetime,timezone
from functools import wraps
from uuid import uuid4
from sqlalchemy import select,func
from sqlalchemy.exc import SQLAlchemyError,IntegrityError
from app.core.database import SessionLocal
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.services.demo_subscriptions import DemoStorageUnavailable
from app.models.router_workspace import RouterWorkspaceRecord as Record,RouterWorkspaceAudit as Audit
from app.integrations.cebeci_access import verified_tls_context

class WorkspaceError(Exception):
    def __init__(self,status,detail):self.status=status;self.detail=detail

def guard(session):
    PostgresDemoStore(session.get_bind())._verify(session.connection())

def boundary(method):
    @wraps(method)
    def call(*args,**kwargs):
        try:return method(*args,**kwargs)
        except IntegrityError:raise WorkspaceError(409,'Kayıt aynı anda değişti. Listeyi yenileyin.') from None
        except (SQLAlchemyError,DemoStorageUnavailable):raise WorkspaceError(503,'Yerel router çalışma alanı hazır değil. V2 migration 007 gerekli; veri belleğe kaydedilmedi.') from None
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
