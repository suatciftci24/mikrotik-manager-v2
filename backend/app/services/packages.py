"""Persistent catalog with optimistic revisions and atomic UUID/audit receipts."""
import hashlib,json
from datetime import datetime,timezone
from sqlalchemy import select,func
from app.core.database import SessionLocal
from app.services.subscriber_listing import search_expression,search_key
from app.models.package import Package,PackageEvent
from app.models.subscriber_workspace import SyntheticSubscriber
from app.services.router_workspace import guard,boundary,WorkspaceError


def public(row):return dict(id=row.id,revision=row.revision,fields=row.fields,is_demo=True)

def binding(session,id,revision):
    row=session.get(Package,id,with_for_update=True)
    if not row:raise WorkspaceError(404,'Kayıtlı paket bulunamadı.')
    if row.revision!=revision:raise WorkspaceError(409,'Paket değişti; yeniden seçip önizleyin.')
    if row.fields.get('active') is not True:raise WorkspaceError(409,'Pasif paket yeni aboneliğe atanamaz.')
    return dict(plan=row.fields['name'],package_id=row.id,package_revision=row.revision,package_snapshot=dict(row.fields))

def command_fingerprint(actor, id, payload):
    data = json.dumps([actor,id,payload],sort_keys=True,separators=(',',':'))
    return hashlib.sha256(data.encode()).hexdigest()


def package_links():
    return SyntheticSubscriber.fields['package_id'].as_string()


class Packages:
    def __init__(self,sessions=SessionLocal,check=guard):self.sessions=sessions;self.check=check
    @boundary
    def list(self,page=1,page_size=100,include_inactive=False,*,query='',status='ALL'):
        with self.sessions() as session:
            if session.get_bind().dialect.name == 'postgresql':
                session.connection(execution_options={'isolation_level':'REPEATABLE READ','postgresql_readonly':True})
            self.check(session)
            clauses=[]
            if not include_inactive or status == 'ACTIVE':
                clauses.append(Package.fields['active'].as_boolean().is_(True))
            elif status == 'INACTIVE':
                clauses.append(Package.fields['active'].as_boolean().is_(False))
            if query.strip():
                clauses.append(search_expression(session)(Package.name_key).contains(search_key(query.strip()),autoescape=True))
            total=session.scalar(select(func.count()).select_from(Package).where(*clauses))
            rows=session.scalars(select(Package).where(*clauses).order_by(Package.name_key,Package.id).offset((page-1)*page_size).limit(page_size)).all()
            counts = {}
            if include_inactive and rows:
                link = package_links()
                counts = dict(session.execute(
                    select(link, func.count()).where(link.in_([row.id for row in rows])).group_by(link)
                ).all())
            items = [{**public(row), **({'subscriber_count':counts.get(row.id,0)} if include_inactive else {})} for row in rows]
            return dict(items=items,total=total,page=page,page_size=page_size,is_demo=True)
    @boundary
    def save(self,command,actor,id=None):
        fields=command.fields.model_dump(mode='json');target=id or 'demo-package-'+str(command.request_id)
        payload = command.model_dump(mode='json')
        fingerprint = command_fingerprint(actor,id,payload)
        fingerprints = {fingerprint}
        if fields['currency'] == 'TRY' and fields['radius_policy_ref'] is None:
            legacy_fields = {key:value for key,value in fields.items() if key not in ('currency','radius_policy_ref')}
            fingerprints.add(command_fingerprint(actor,id,{**payload,'fields':legacy_fields}))
        with self.sessions.begin() as session:
            self.check(session)
            row=session.get(Package,target,with_for_update=True)
            prior=session.get(PackageEvent,str(command.request_id))
            if prior:
                if prior.actor_id!=actor or prior.package_id!=target or prior.changes.get('action')=='DELETE' or prior.changes.get('fingerprint') not in fingerprints:raise WorkspaceError(409,'Paket istek kimliği başka bir işleme ait.')
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
    def delete(self, id, command, actor):
        fingerprint = command_fingerprint(actor,id,{'action':'DELETE',**command.model_dump(mode='json')})
        with self.sessions.begin() as session:
            self.check(session)
            # Assignments acquire this same lock before storing the package ID.
            row = session.get(Package,id,with_for_update=True)
            request_id = str(command.request_id)
            prior = session.get(PackageEvent,request_id)
            if prior:
                if (prior.actor_id!=actor or prior.package_id!=id or
                        prior.changes.get('action')!='DELETE' or prior.changes.get('fingerprint')!=fingerprint):
                    raise WorkspaceError(409,'Paket istek kimliği başka bir işleme ait.')
                return prior.changes['response']
            if row is None:
                raise WorkspaceError(404,'Paket bulunamadı.')
            if row.revision != command.expected_revision:
                raise WorkspaceError(409,'Paket değişti; güncel kaydı açın.')
            if session.scalar(select(SyntheticSubscriber.id).where(package_links()==id).limit(1)) is not None:
                raise WorkspaceError(409,'Pakete bağlı aboneler var. Paket silinemez.')
            result = dict(id=id,request_id=request_id,deleted=True,is_demo=True)
            session.add(PackageEvent(id=request_id,package_id=id,actor_id=actor,revision=row.revision+1,
                occurred_at=datetime.now(timezone.utc).isoformat(),
                changes=dict(action='DELETE',previous=dict(row.fields),values=None,fingerprint=fingerprint,response=result)))
            session.delete(row)
            session.flush()
            return result

    @boundary
    def history(self,id):
        with self.sessions() as session:
            self.check(session)
            rows=session.scalars(select(PackageEvent).where(PackageEvent.package_id==id).order_by(PackageEvent.occurred_at.desc(),PackageEvent.id).limit(50)).all()
            if not rows and session.get(Package,id) is None:raise WorkspaceError(404,'Paket bulunamadı.')
            return dict(items=[dict(action=row.changes.get('action'),request_id=row.id,actor_id=row.actor_id,revision=row.revision,occurred_at=row.occurred_at,previous=row.changes['previous'],values=row.changes['values']) for row in rows],is_demo=True)

packages=Packages()
