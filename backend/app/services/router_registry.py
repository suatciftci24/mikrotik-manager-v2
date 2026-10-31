"""Transactional onboarding: bounded probe -> short-lived actor-bound proof -> confirm.

DB/audit never contain credentials. Proof retry returns saved state, never reconnects.
"""
from datetime import datetime,timedelta,timezone
from functools import wraps
from uuid import uuid4
from sqlalchemy import select,func,or_,update
from sqlalchemy.exc import SQLAlchemyError,IntegrityError
from app.core.database import SessionLocal
from app.models.router_registry import RegisteredRouter,RouterVerification,RouterRegistryAudit
from app.adapters.cebeci_api_ssl import ApiSslStop
from app.adapters.router_api_ssl import ConnectionPolicy,RouterApiSslClient,Target
from app.adapters.router_secrets import RouterSecretVault
from app.integrations.cebeci_access import verified_tls_context


def now():return datetime.now(timezone.utc)
def stamp():return now().isoformat()

class RegistryError(Exception):
    def __init__(self,status,code):self.status=status;self.code=code


def storage_boundary(method):
    @wraps(method)
    def call(*args,**kwargs):
        try:return method(*args,**kwargs)
        except RegistryError:raise
        except ApiSslStop as error:raise RegistryError(409,str(error)) from None
        except SQLAlchemyError:raise RegistryError(503,'REGISTRY_STORAGE_UNAVAILABLE') from None
    return call


def pending(row):
    return row.configuration.get('onboarding_state')=='PENDING_VERIFICATION'


def require_verified_inventory(row):
    if pending(row):raise RegistryError(409,'ROUTER_PENDING_VERIFICATION')


def public_router(row):
    if pending(row):
        return dict(id=row.id,name=row.name,management_address=row.management_address,port=row.port,
            identity=None,model=row.metadata_snapshot.get('model'),routeros_version=row.metadata_snapshot.get('routeros_version'),
            inventory_information=row.metadata_snapshot,revision=row.revision,last_checked_at=None,last_success_at=None,
            last_error=None,status='PENDING_VERIFICATION',leaf_sha256='',source_ip='',expected_identity='',expected_version='',
            credentials_configured=True,pilot_kind=None,is_demo=False,continuous_monitoring=False)
    checked=datetime.fromisoformat(row.last_success_at)
    state='CHECK_FAILED' if row.last_error else 'STALE' if now()-checked>timedelta(minutes=5) else 'VERIFIED'
    return dict(id=row.id,name=row.name,management_address=row.management_address,port=row.port,
        **row.metadata_snapshot,revision=row.revision,last_checked_at=row.last_checked_at,
        last_success_at=row.last_success_at,last_error=row.last_error,status=state,
        leaf_sha256=row.configuration['leaf_sha256'],source_ip=row.configuration['source_ip'],
        expected_identity=row.configuration['expected_identity'],expected_version=row.configuration['expected_version'],
        credentials_configured=True,pilot_kind=row.configuration.get('pilot_kind'),is_demo=False,continuous_monitoring=False)


class RouterRegistry:
    def __init__(self,sessions=SessionLocal,vault=None,client=None,policy=None):
        self.sessions=sessions;self.vault=vault or RouterSecretVault();self.client=client or RouterApiSslClient()
        self.policy=policy or ConnectionPolicy.environment

    @storage_boundary
    def inventory(self,payload,actor):
        command=payload.model_dump(mode='json',exclude={'request_id','confirmed'})
        key=str(payload.request_id)
        try:
            with self.sessions.begin() as session:
                prior=session.get(RouterRegistryAudit,key)
                if prior:
                    if prior.actor_id!=actor or prior.action!='INVENTORY_REGISTERED' or prior.details.get('command')!=command:
                        raise RegistryError(409,'INVENTORY_REQUEST_CONFLICT')
                    return dict(item=public_router(session.get(RegisteredRouter,prior.router_id)),replayed=True,is_demo=False)
                duplicate=session.scalar(select(RegisteredRouter.id).where(RegisteredRouter.management_address==command['management_address'],RegisteredRouter.port==payload.port))
                if duplicate:raise RegistryError(409,'ROUTER_ENDPOINT_EXISTS')
                # Resolve only the existing V2 vault. Never create/copy credentials or consult connection policy.
                self.vault.read(str(payload.credential_ref))
                row=RegisteredRouter(id='registered-'+str(uuid4()),name=payload.name,
                    management_address=command['management_address'],port=payload.port,
                    configuration={'onboarding_state':'PENDING_VERIFICATION'},
                    metadata_snapshot={field:command[field] for field in ('description','site','model','routeros_version')},
                    credential_ref=str(payload.credential_ref),revision=1,
                    # Existing schema is NOT NULL: empty means never observed; API publishes null.
                    last_checked_at='',last_success_at='',last_error=None)
                session.add(row)
                self.audit(session,actor,key,'INVENTORY_REGISTERED',row.id,audit_id=key,command=command,state='PENDING_VERIFICATION')
                session.flush()
                result=dict(item=public_router(row),replayed=False,is_demo=False)
            return result
        except IntegrityError:
            raise RegistryError(409,'INVENTORY_CONFLICT') from None

    @staticmethod
    def audit(session,actor,verification,action,router_id=None,audit_id=None,**details):
        session.add(RouterRegistryAudit(id=audit_id or str(uuid4()),actor_id=actor,verification_id=verification,
            action=action,router_id=router_id,occurred_at=stamp(),details=details))

    @staticmethod
    def proof(row):
        result=dict(verification_id=row.id,state=row.state,expires_at=row.expires_at,error_code=row.error_code,
            saved_router_id=row.saved_router_id,is_demo=False)
        if row.state=='VERIFIED' and now()>datetime.fromisoformat(row.expires_at):
            result.update(state='EXPIRED',error_code='VERIFICATION_EXPIRED')
            return result
        if row.state in ('VERIFIED','SAVED'):
            snapshot=row.snapshot
            result['preview']={key:snapshot[key] for key in ('name','management_address','port','metadata','source_ip','checked_at','expected_revision')}
        return result

    @storage_boundary
    def verify_pilot(self,payload,actor):
        with self.sessions() as session:
            prior=session.get(RouterVerification,str(payload.request_id))
            if prior:
                if prior.actor_id!=actor or prior.snapshot.get('kind')=='DETAIL_READ' or prior.snapshot.get('management_address')!='10.250.0.19' or prior.snapshot.get('configuration',{}).get('pilot_kind')!='CEBECI_TOWERS':raise RegistryError(409,'VERIFICATION_REQUEST_CONFLICT')
                return self.proof(prior)
            if session.scalar(select(RegisteredRouter.id).where(RegisteredRouter.management_address=='10.250.0.19',RegisteredRouter.port==8729)):raise RegistryError(409,'ROUTER_ENDPOINT_EXISTS')
        from app.services.cebeci_registry import candidate
        command=candidate(payload,self.policy())
        return self.verify(command,actor)

    @storage_boundary
    def read_details(self,id,payload,actor):
        key=str(payload.request_id)
        with self.sessions() as session:
            prior=session.get(RouterVerification,key)
            if prior:
                if prior.actor_id!=actor or prior.target_router_id!=id or prior.snapshot.get('kind')!='DETAIL_READ':raise RegistryError(409,'VERIFICATION_REQUEST_CONFLICT')
                return prior.snapshot.get('result',dict(state='RUNNING',error_code='VERIFICATION_IN_PROGRESS',is_demo=False))
            row=session.get(RegisteredRouter,id)
            if not row:raise RegistryError(404,'ROUTER_NOT_FOUND')
            require_verified_inventory(row)
            if row.revision!=payload.expected_revision:raise RegistryError(409,'ROUTER_REVISION_CONFLICT')
            if row.configuration.get('pilot_kind')!='CEBECI_TOWERS':raise RegistryError(403,'PILOT_SCOPE_MISMATCH')
            policy=self.policy();policy.validate(row.management_address,row.port)
            config=row.configuration;reference=row.credential_ref
            target=Target(row.management_address,row.port,config['ca_pem'],config['leaf_sha256'],config['expected_identity'],config['expected_version'],config['expected_model'])
        with self.sessions.begin() as session:
            session.add(RouterVerification(id=key,actor_id=actor,state='RUNNING',target_router_id=id,expected_revision=payload.expected_revision,snapshot={'kind':'DETAIL_READ'},credential_ref=reference,created_at=stamp(),expires_at=(now()+timedelta(minutes=5)).isoformat()))
            self.audit(session,actor,key,'READ_ONLY_REQUESTED',id)
        error=None;snapshot=None
        try:
            from app.schemas.router_readonly import ReadOnlySnapshot
            snapshot=ReadOnlySnapshot.model_validate(self.client.read_snapshot(target,self.vault.read(reference),policy)).model_dump(mode='json',by_alias=True)
        except ApiSslStop as failure:error=str(failure)
        except Exception:error='API_SSL_STOP'
        with self.sessions.begin() as session:
            row=session.get(RegisteredRouter,id,with_for_update=True);proof=session.get(RouterVerification,key,with_for_update=True)
            if not row or row.revision!=payload.expected_revision:error='ROUTER_REVISION_CONFLICT'
            if row and row.revision==payload.expected_revision:
                row.last_checked_at=stamp();row.last_error=error;row.revision+=1
                if not error:row.metadata_snapshot={**row.metadata_snapshot,'read_snapshot':snapshot};row.last_success_at=snapshot['captured_at']
            proof.state='FAILED' if error else 'SAVED';proof.error_code=error;proof.saved_router_id=id if not error else None
            result=dict(state=proof.state,error_code=error,item=public_router(row) if row else None,is_demo=False)
            proof.snapshot={'kind':'DETAIL_READ','result':result}
            self.audit(session,actor,key,'READ_ONLY_FAILED' if error else 'READ_ONLY_SAVED',id,error_code=error)
        return result

    @storage_boundary
    def list(self,query='',status='ALL',page=1,page_size=25):
        with self.sessions() as session:
            clause=[]
            if query:
                term='%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                clause.append(or_(RegisteredRouter.name.ilike(term,escape='\\'),RegisteredRouter.management_address.ilike(term,escape='\\'),RegisteredRouter.metadata_snapshot['model'].as_string().ilike(term,escape='\\'),RegisteredRouter.metadata_snapshot['identity'].as_string().ilike(term,escape='\\'),RegisteredRouter.metadata_snapshot['routeros_version'].as_string().ilike(term,escape='\\')))
            pending_clause=RegisteredRouter.configuration['onboarding_state'].as_string()=='PENDING_VERIFICATION'
            if status=='PENDING_VERIFICATION':clause.append(pending_clause)
            elif status!='ALL':clause.append(or_(RegisteredRouter.configuration['onboarding_state'].as_string().is_(None),RegisteredRouter.configuration['onboarding_state'].as_string()!='PENDING_VERIFICATION'))
            cutoff=(now()-timedelta(minutes=5)).isoformat()
            if status=='CHECK_FAILED':clause.append(RegisteredRouter.last_error.is_not(None))
            elif status=='STALE':clause.extend((RegisteredRouter.last_error.is_(None),RegisteredRouter.last_success_at<cutoff))
            elif status=='VERIFIED':clause.extend((RegisteredRouter.last_error.is_(None),RegisteredRouter.last_success_at>=cutoff))
            total=session.scalar(select(func.count()).select_from(RegisteredRouter).where(*clause))
            rows=session.scalars(select(RegisteredRouter).where(*clause).order_by(RegisteredRouter.name,RegisteredRouter.id).offset((page-1)*page_size).limit(page_size)).all()
            return dict(items=[public_router(row) for row in rows],total=total,page=page,page_size=page_size,is_demo=False)

    @storage_boundary
    def detail(self,id):
        with self.sessions() as session:
            row=session.get(RegisteredRouter,id)
            if row is None:raise RegistryError(404,'ROUTER_NOT_FOUND')
            events=session.scalars(select(RouterRegistryAudit).where(RouterRegistryAudit.router_id==id).order_by(RouterRegistryAudit.occurred_at.desc()).limit(50)).all()
            return dict(item=public_router(row),history=[dict(action=e.action,occurred_at=e.occurred_at,actor_id=e.actor_id,details=e.details) for e in events],is_demo=False)

    @storage_boundary
    def verify(self,payload,actor):
        request_id=str(payload.request_id)
        with self.sessions() as session:
            prior=session.get(RouterVerification,request_id)
            if prior:
                if prior.snapshot.get('kind')=='DETAIL_READ':raise RegistryError(409,'VERIFICATION_REQUEST_CONFLICT')
                if prior.actor_id!=actor:raise RegistryError(409,'VERIFICATION_REQUEST_CONFLICT')
                return self.proof(prior)
            old=session.get(RegisteredRouter,payload.router_id) if payload.router_id else None
            if old:require_verified_inventory(old)
            if payload.router_id and old is None:raise RegistryError(404,'ROUTER_NOT_FOUND')
            if payload.expected_revision!=(old.revision if old else 0):raise RegistryError(409,'ROUTER_REVISION_CONFLICT')
            duplicate=session.scalar(select(RegisteredRouter.id).where(RegisteredRouter.management_address==str(payload.management_address),RegisteredRouter.port==payload.port))
            if duplicate and duplicate!=payload.router_id:raise RegistryError(409,'ROUTER_ENDPOINT_EXISTS')
            policy=self.policy();policy.validate(str(payload.management_address),payload.port)
            ca=payload.ca_pem or (old.configuration['ca_pem'] if old else '')
            try:verified_tls_context(ca)
            except ValueError:raise RegistryError(422,'CA_CERTIFICATE_REJECTED') from None
            if old and (not payload.username or payload.password is None):
                stored_name,stored_password=self.vault.read(old.credential_ref)
            else:stored_name=stored_password=''
            username=payload.username or stored_name
            password=payload.password.get_secret_value() if payload.password is not None else stored_password
            self.vault.valid(username,password)
            config=dict(ca_pem=ca,leaf_sha256=payload.leaf_sha256,source_ip=policy.source_ip,
                expected_identity=payload.expected_identity or (old.metadata_snapshot['identity'] if old else ''),
                expected_version=payload.expected_version,expected_model=old.metadata_snapshot['model'] if old else payload.expected_model)
            if (str(payload.management_address),payload.port,username,config['expected_identity'],config['expected_model'],config['expected_version'],policy.source_ip)==('10.250.0.19',8729,'v2-cebeci-ro','CEBECI_TOWERS','RB3011UiAS','6.49.19','10.250.0.1'):config['pilot_kind']='CEBECI_TOWERS'
            snapshot=dict(name=payload.name,management_address=str(payload.management_address),port=payload.port,
                configuration=config,source_ip=policy.source_ip,expected_revision=payload.expected_revision)
        reference=self.vault.put(username,password)
        created=now()
        try:
            with self.sessions.begin() as session:
                session.add(RouterVerification(id=request_id,actor_id=actor,state='RUNNING',target_router_id=payload.router_id,
                    expected_revision=payload.expected_revision,snapshot=snapshot,credential_ref=reference,
                    created_at=created.isoformat(),expires_at=(created+timedelta(minutes=5)).isoformat()))
                self.audit(session,actor,request_id,'PROBE_REQUESTED',payload.router_id,address=snapshot['management_address'],port=payload.port)
        except IntegrityError:
            self.vault.discard(reference)
            with self.sessions() as session:
                prior=session.get(RouterVerification,request_id)
                if prior and prior.actor_id==actor:return self.proof(prior)
            raise RegistryError(409,'VERIFICATION_REQUEST_CONFLICT') from None
        except Exception:
            self.vault.discard(reference);raise
        error=None;metadata=None
        try:
            metadata=self.client.probe(Target(snapshot['management_address'],snapshot['port'],ca,payload.leaf_sha256,config['expected_identity'],config['expected_version'],config['expected_model']),(username,password),policy)
        except ApiSslStop as failure:error=str(failure)
        except Exception:error='API_SSL_STOP'
        finally:del password,stored_password
        with self.sessions.begin() as session:
            proof=session.get(RouterVerification,request_id,with_for_update=True)
            proof.state='FAILED' if error else 'VERIFIED';proof.error_code=error
            proof.snapshot={**snapshot,'metadata':metadata,'checked_at':stamp()}
            self.audit(session,actor,request_id,'PROBE_FAILED' if error else 'PROBE_VERIFIED',payload.router_id,error_code=error)
            if error and payload.router_id:
                row=session.get(RegisteredRouter,payload.router_id,with_for_update=True)
                if row and row.revision==payload.expected_revision:
                    row.last_error=error;row.last_checked_at=stamp();row.revision+=1
            result=self.proof(proof)
        if error:self.vault.discard(reference)
        return result

    @storage_boundary
    def register(self,payload,actor):
        old_reference=None
        with self.sessions.begin() as session:
            proof=session.get(RouterVerification,str(payload.verification_id),with_for_update=True)
            if not proof or proof.actor_id!=actor:raise RegistryError(404,'VERIFICATION_NOT_FOUND')
            if proof.snapshot.get('kind')=='DETAIL_READ':raise RegistryError(409,'VERIFICATION_REQUEST_CONFLICT')
            if proof.state=='SAVED':
                row=session.get(RegisteredRouter,proof.saved_router_id)
                return dict(item=public_router(row),replayed=True,is_demo=False)
            if proof.state!='VERIFIED':raise RegistryError(409,'VERIFICATION_NOT_SUCCESSFUL')
            if now()>datetime.fromisoformat(proof.expires_at):raise RegistryError(409,'VERIFICATION_EXPIRED')
            value=proof.snapshot;policy=self.policy();policy.validate(value['management_address'],value['port'])
            if policy.source_ip!=value['source_ip']:raise RegistryError(409,'CONNECTION_POLICY_CHANGED')
            # Ensure the exact verified material still exists; no second connection on save.
            self.vault.read(proof.credential_ref)
            row=session.get(RegisteredRouter,proof.target_router_id,with_for_update=True) if proof.target_router_id else None
            if proof.target_router_id and row is None:raise RegistryError(404,'ROUTER_NOT_FOUND')
            if row:require_verified_inventory(row)
            if row and row.revision!=proof.expected_revision:raise RegistryError(409,'ROUTER_REVISION_CONFLICT')
            duplicate=session.scalar(select(RegisteredRouter.id).where(RegisteredRouter.management_address==value['management_address'],RegisteredRouter.port==value['port']))
            if duplicate and (row is None or duplicate!=row.id):raise RegistryError(409,'ROUTER_ENDPOINT_EXISTS')
            action='ROUTER_UPDATED' if row else 'ROUTER_REGISTERED'
            if row:old_reference=row.credential_ref
            else:
                row=RegisteredRouter(id='registered-'+str(uuid4()),revision=0)
                session.add(row)
            for field in ('name','management_address','port','configuration'):
                setattr(row,field,value[field])
            row.configuration={**row.configuration,'expected_identity':value['metadata']['identity']}
            row.metadata_snapshot=value['metadata'];row.credential_ref=proof.credential_ref
            row.revision+=1;row.last_checked_at=value['checked_at'];row.last_success_at=value['checked_at'];row.last_error=None
            proof.state='SAVED';proof.saved_router_id=row.id
            session.execute(update(RouterRegistryAudit).where(RouterRegistryAudit.verification_id==proof.id,RouterRegistryAudit.router_id.is_(None)).values(router_id=row.id))
            self.audit(session,actor,proof.id,action,row.id,revision=row.revision)
            result=dict(item=public_router(row),replayed=False,is_demo=False)
            new_reference=proof.credential_ref
            if old_reference and old_reference!=new_reference:
                session.flush()
                if session.scalar(select(RegisteredRouter.id).where(RegisteredRouter.credential_ref==old_reference)):
                    old_reference=None
        if old_reference and old_reference!=new_reference:
            try:self.vault.discard(old_reference)
            except ApiSslStop:pass  # Committed registry/audit stays successful; no credential is exposed.
        return result

    @storage_boundary
    def recheck(self,id,payload,actor):
        from app.schemas.router_registry import RouterCandidate,RegisterVerified
        with self.sessions() as session:
            prior=session.get(RouterVerification,str(payload.request_id))
            if prior:
                if prior.snapshot.get('kind')=='DETAIL_READ':raise RegistryError(409,'VERIFICATION_REQUEST_CONFLICT')
                if prior.actor_id!=actor or prior.target_router_id!=id:raise RegistryError(409,'VERIFICATION_REQUEST_CONFLICT')
                result=self.proof(prior)
            else:result=None
        if result is None:
            item=self.detail(id)['item']
            if item['status']=='PENDING_VERIFICATION':raise RegistryError(409,'ROUTER_PENDING_VERIFICATION')
            if item['revision']!=payload.expected_revision:raise RegistryError(409,'ROUTER_REVISION_CONFLICT')
            candidate=RouterCandidate(request_id=payload.request_id,name=item['name'],management_address=item['management_address'],
                port=item['port'],expected_identity=item['identity'],expected_version=item['expected_version'],
                leaf_sha256=item['leaf_sha256'],router_id=id,expected_revision=item['revision'],confirmed_read_only=True)
            result=self.verify(candidate,actor)
        if result['state'] in ('VERIFIED','SAVED'):
            return self.register(RegisterVerified(verification_id=payload.request_id,confirmed=True),actor)
        return result

    @storage_boundary
    def cancel(self,verification_id,actor):
        reference=None
        with self.sessions.begin() as session:
            proof=session.get(RouterVerification,verification_id,with_for_update=True)
            if not proof or proof.actor_id!=actor:raise RegistryError(404,'VERIFICATION_NOT_FOUND')
            if proof.state=='RUNNING':raise RegistryError(409,'VERIFICATION_IN_PROGRESS')
            if proof.state=='VERIFIED':
                reference=proof.credential_ref;proof.state='CANCELLED'
                self.audit(session,actor,proof.id,'PROBE_CANCELLED',proof.target_router_id)
        if reference:self.vault.discard(reference)
        return dict(cancelled=True,is_demo=False)


registry=RouterRegistry()
