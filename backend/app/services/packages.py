"""Persistent catalog with optimistic revisions and atomic UUID/audit receipts."""
import hashlib,json
from datetime import datetime,timezone
from sqlalchemy import select,func
from app.core.database import SessionLocal
from app.models.package import Package,PackageEvent
from app.services.router_workspace import guard,boundary,WorkspaceError


def public(row):return dict(id=row.id,revision=row.revision,fields=row.fields,is_demo=True)

def binding(session,id,revision):
    row=session.get(Package,id,with_for_update=True)
    if not row:raise WorkspaceError(404,'Kayıtlı paket bulunamadı.')
    if row.revision!=revision:raise WorkspaceError(409,'Paket değişti; yeniden seçip önizleyin.')
    if row.fields.get('active') is not True:raise WorkspaceError(409,'Pasif paket yeni aboneliğe atanamaz.')
    return dict(plan=row.fields['name'],package_id=row.id,package_revision=row.revision,package_snapshot=dict(row.fields))

class Packages:
    def __init__(self,sessions=SessionLocal,check=guard):self.sessions=sessions;self.check=check
    @boundary
    def list(self,page=1,page_size=100,include_inactive=False):
        with self.sessions() as session:
            self.check(session)
            clauses=[] if include_inactive else [Package.fields['active'].as_boolean().is_(True)]
            total=session.scalar(select(func.count()).select_from(Package).where(*clauses))
            rows=session.scalars(select(Package).where(*clauses).order_by(Package.name_key,Package.id).offset((page-1)*page_size).limit(page_size)).all()
            return dict(items=[public(row) for row in rows],total=total,page=page,page_size=page_size,is_demo=True)
    @boundary
    def save(self,command,actor,id=None):
        fields=command.fields.model_dump(mode='json');target=id or 'demo-package-'+str(command.request_id)
        fingerprint=hashlib.sha256(json.dumps([actor,id,command.model_dump(mode='json')],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self.sessions.begin() as session:
            self.check(session)
            row=session.get(Package,target,with_for_update=True)
            prior=session.get(PackageEvent,str(command.request_id))
            if prior:
                if prior.actor_id!=actor or prior.package_id!=target or prior.changes.get('fingerprint')!=fingerprint:raise WorkspaceError(409,'Paket istek kimliği başka bir işleme ait.')
                return prior.changes['response']
            if id and not row:raise WorkspaceError(404,'Paket bulunamadı.')
            if command.expected_revision!=(row.revision if row else 0):raise WorkspaceError(409,'Paket değişti; güncel kaydı açın.')
            duplicate=session.scalar(select(Package.id).where(Package.name_key==fields['name'].casefold(),Package.id!=target))
            if duplicate:raise WorkspaceError(409,'Bu paket adı zaten kayıtlı.')
            before=dict(row.fields) if row else None
            if row is None:
                row=Package(id=target,revision=0);session.add(row)
            row.name_key=fields['name'].casefold();row.fields=fields;row.revision+=1
            response=public(row)
            session.add(PackageEvent(id=str(command.request_id),package_id=target,actor_id=actor,revision=row.revision,occurred_at=datetime.now(timezone.utc).isoformat(),changes=dict(previous=before,values=fields,fingerprint=fingerprint,response=response)))
            session.flush()
            return response
    @boundary
    def history(self,id):
        with self.sessions() as session:
            self.check(session)
            if session.get(Package,id) is None:raise WorkspaceError(404,'Paket bulunamadı.')
            rows=session.scalars(select(PackageEvent).where(PackageEvent.package_id==id).order_by(PackageEvent.occurred_at.desc(),PackageEvent.id).limit(50)).all()
            return dict(items=[dict(request_id=row.id,actor_id=row.actor_id,revision=row.revision,occurred_at=row.occurred_at,previous=row.changes['previous'],values=row.changes['values']) for row in rows],is_demo=True)

packages=Packages()
