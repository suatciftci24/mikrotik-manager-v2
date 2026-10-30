"""Isolated V2 identities. Account origin is separate from the synthetic data environment."""
import hashlib
import hmac
import secrets
import json
from uuid import uuid4
from pathlib import Path
from sqlalchemy import text
from app.services.identity_setup import inspect_setup
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from typing import Literal
from app.core.authorization import PERMISSIONS, WRITE_FLAGS
from app.services.demo_data import ROUTERS
from app.adapters.demo_subscriptions import storage_errors
from app.services.demo_subscriptions import DemoChangeError,DemoStorageUnavailable


def local_password_valid(password):
    return (14<=len(password)<=128 and len(password.encode('utf-8'))<=1024
            and bool(password.strip()) and not any(c in password for c in ('\r','\n','\0')))


def hash_password(password,*,real_account=False):
    salt=secrets.token_bytes(16)
    n=131072 if real_account else 32768
    digest=hashlib.scrypt(password.encode(),salt=salt,n=n,r=8,p=1,dklen=32,maxmem=256*1024*1024)
    return f'scrypt${n}$8$1$'+salt.hex()+'$'+digest.hex()


def verify_password(password,encoded):
    try:
        algorithm,n,r,p,salt,digest=encoded.split('$')
        if algorithm!='scrypt' or n not in ('32768','131072') or (r,p)!=('8','1'):return False
        salt,digest=bytes.fromhex(salt),bytes.fromhex(digest)
        if len(salt)!=16 or len(digest)!=32:return False
        actual=hashlib.scrypt(password.encode(),salt=salt,n=int(n),r=8,p=1,dklen=32,maxmem=256*1024*1024)
        return hmac.compare_digest(actual,digest)
    except (ValueError,TypeError):return False

BOOTSTRAP_HASH=hash_password('demo-only')

def bootstrap():
    return dict(id='demo-user',username='demo',name='Demo Operatör',email='demo@local.test',role='ADMIN',active=True,password_hash=BOOTSTRAP_HASH,
                permissions={r['id']:{p:True for p in PERMISSIONS} for r in ROUTERS},revision=0)


def public_user(user,management=False,*,bootstrap_closed=None):
    closed=user.get('bootstrap_closed',False) if bootstrap_closed is None else bootstrap_closed
    origin='BOOTSTRAP_DEMO' if user['id']=='demo-user' else 'LOCAL' if closed and user.get('account_origin')=='LOCAL' else 'DEMO'
    login_enabled=bool(user['active'] and (not closed or origin=='LOCAL'))
    return {**{k:user[k] for k in ('id','username','name','email','active','revision')},'role_code':user['role'],
            'role':'Sistem Yöneticisi' if user['role']=='ADMIN' else 'Gözlemci','is_demo':True,
            'account_origin':origin,'bootstrap_closed':bool(closed),'login_enabled':login_enabled,
            'can_manage_users':user['role']=='ADMIN' and login_enabled and all(user['permissions'].get(r['id'],{}).get('can_view') is True for r in ROUTERS),
            'permissions':{id:grant for id,grant in user['permissions'].items() if management or grant.get('can_view') is True}}


def adapter():
    from app.services import demo_subscriptions
    store=demo_subscriptions.store._get()
    if store.schema!='v2_demo':raise DemoStorageUnavailable()
    return store


def ready(connection):
    return bool(connection.execute(text("SELECT to_regclass('v2_demo.users')")).scalar_one())


@storage_errors
def find_user(key,by_username=False):
    store=adapter()
    with store.engine.connect() as connection:
        store._verify(connection)
        state=inspect_setup(connection)
        if not state.users_ready:
            default=bootstrap();return default if key==default['username' if by_username else 'id'] else None
        row=connection.execute(text('SELECT * FROM v2_demo.users WHERE '+('username' if by_username else 'id')+'=:key'),{'key':key}).mappings().one_or_none()
        if row is None:return None
        if state.closed and (row['id']=='demo-user' or row.get('account_origin')!='LOCAL'):return None
        if row.get('account_origin')=='LOCAL' and not state.closed:raise DemoStorageUnavailable()
        return {**row,'bootstrap_closed':state.closed}



class Grant(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    can_view:bool=False
    can_manage_pppoe:bool=False
    can_manage_hotspot:bool=False
    can_view_reports:bool=False
    can_use_mikajani:bool=False
    can_ack_alarms:bool=False

class UserChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str=Field(pattern=r'^[0-9a-fA-F-]{36}$')
    name:str=Field(min_length=1,max_length=120)
    email:str=Field(min_length=1,max_length=180)
    role:Literal['ADMIN','VIEWER']
    active:bool
    permissions:dict[str,Grant]
    expected_revision:int=Field(ge=0)
    confirmed:Literal[True]
    @field_validator('request_id')
    @classmethod
    def valid_request(cls,value):
        from uuid import UUID
        return str(UUID(value))
    @model_validator(mode='after')
    def valid_scope(self):
        if set(self.permissions)-{r['id'] for r in ROUTERS}:raise ValueError('Bilinmeyen router izni')
        if self.role=='VIEWER' and any(getattr(grant,p) for grant in self.permissions.values() for p in WRITE_FLAGS):raise ValueError('VIEWER değişiklik yetkisi alamaz')
        return self

class UserCreate(UserChange):
    username:str=Field(pattern=r'^[a-zA-Z0-9_.-]{3,64}$')
    password:str=Field(min_length=12,max_length=128,repr=False,exclude=True)


def transition(old,payload,actor_id,admin_count):
    if old['revision']!=payload.expected_revision:raise DemoChangeError(409,'Kullanıcı değişmiş; yeniden yükleyin.')
    if old['id']==actor_id and (payload.role!='ADMIN' or not payload.active):raise DemoChangeError(409,'Kendi ADMIN yetkinizi veya aktif durumunuzu kaldıramazsınız.')
    if old['id']==actor_id and not all(payload.permissions.get(r['id']) and payload.permissions[r['id']].can_view for r in ROUTERS):raise DemoChangeError(409,'Kendi merkezi yönetim kapsamınızı kaldıramazsınız.')
    if old['role']=='ADMIN' and old['active'] and (payload.role!='ADMIN' or not payload.active) and admin_count<=1:
        raise DemoChangeError(409,'Son aktif ADMIN korunmalıdır.')
    return {**old,'name':payload.name,'email':payload.email,'role':payload.role,'active':payload.active,
            'permissions':{id:grant.model_dump() for id,grant in payload.permissions.items()},'revision':old['revision']+1}


@storage_errors
def save_user(payload,actor_id,target_id=None):
    store=adapter();fingerprint=json.dumps(payload.model_dump(exclude={'password'}),sort_keys=True)
    with store.engine.begin() as connection:
        store._verify(connection)
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('v2-user-management'))"))
        state=inspect_setup(connection)
        if not state.users_ready:raise DemoChangeError(503,'Kullanıcı deposu hazır değil; users-init açık yerel bakımı gerekli.')
        actor=connection.execute(text('SELECT * FROM v2_demo.users WHERE id=:id'),{'id':actor_id}).mappings().one_or_none()
        if state.closed and actor and (actor['id']=='demo-user' or actor.get('account_origin')!='LOCAL'):raise DemoChangeError(403,'Demo kimliğiyle gerçek kullanıcı yönetilemez.')
        if not actor or not actor['active'] or actor['role']!='ADMIN' or not all(actor['permissions'].get(r['id'],{}).get('can_view') is True for r in ROUTERS):raise DemoChangeError(403,'Yönetici yetkisi gerekli')
        receipt=connection.execute(text('SELECT * FROM v2_demo.user_audit WHERE id=:id'),{'id':payload.request_id}).mappings().one_or_none()
        operation='UPDATE' if target_id else 'CREATE'
        if receipt:
            if receipt['actor_id']!=actor_id or receipt['operation']!=operation or receipt['fingerprint']!=fingerprint or target_id and receipt['target_id']!=target_id:
                raise DemoChangeError(409,'İstek kimliği farklı kullanıcı işlemi için kullanılmış.')
            if receipt['result']!='SUCCESS':raise DemoChangeError(receipt['response']['status'],receipt['response']['detail'])
            if not target_id:
                saved=connection.execute(text('SELECT password_hash FROM v2_demo.users WHERE id=:id'),{'id':receipt['target_id']}).scalar_one()
                if not verify_password(payload.password,saved):raise DemoChangeError(409,'İstek kimliği farklı kullanıcı işlemi için kullanılmış.')
            return receipt['response']
        if target_id:
            old=connection.execute(text('SELECT * FROM v2_demo.users WHERE id=:id FOR UPDATE'),{'id':target_id}).mappings().one_or_none()
            if not old:raise DemoChangeError(404,'Kayıt bulunamadı')
            count=connection.execute(text("SELECT count(*) FROM v2_demo.users WHERE role='ADMIN' AND active"+(" AND account_origin='LOCAL'" if state.closed else ''))).scalar_one()
            new=transition(dict(old),payload,actor_id,count)
        else:
            if connection.execute(text('SELECT 1 FROM v2_demo.users WHERE username=:name'),{'name':payload.username}).scalar_one_or_none():raise DemoChangeError(409,'Kullanıcı adı kullanılamıyor.')
            origin='LOCAL' if state.closed and actor.get('account_origin')=='LOCAL' else 'DEMO'
            if origin=='LOCAL' and not local_password_valid(payload.password):raise DemoChangeError(422,'Parola 14–128 karakter olmalı ve satır sonu içermemeli.')
            old=None;new=dict(id=('v2-user-' if origin=='LOCAL' else 'demo-user-')+str(uuid4()),account_origin=origin,username=payload.username,name=payload.name,email=payload.email,role=payload.role,active=payload.active,
               permissions={id:g.model_dump() for id,g in payload.permissions.items()},revision=0,password_hash=hash_password(payload.password,real_account=origin=='LOCAL'))
        params={**new,'permissions':json.dumps(new['permissions'])}
        if old:connection.execute(text('UPDATE v2_demo.users SET name=:name,email=:email,role=:role,active=:active,permissions=CAST(:permissions AS jsonb),revision=:revision WHERE id=:id'),params)
        else:
            columns=',account_origin' if state.modern else ''
            values=',:account_origin' if state.modern else ''
            connection.execute(text('INSERT INTO v2_demo.users(id,username,name,email,role,active,password_hash,permissions,revision'+columns+') VALUES (:id,:username,:name,:email,:role,:active,:password_hash,CAST(:permissions AS jsonb),:revision'+values+')'),params)
        response=public_user(new,True,bootstrap_closed=state.closed)
        connection.execute(text('''INSERT INTO v2_demo.user_audit(id,actor_id,target_id,operation,previous_values,new_values,result,fingerprint,response)
          VALUES (:id,:actor,:target,:operation,CAST(:previous AS jsonb),CAST(:new AS jsonb),'SUCCESS',:fingerprint,CAST(:response AS jsonb))'''),
          dict(id=payload.request_id,actor=actor_id,target=new['id'],operation=operation,previous=json.dumps(public_user(old,True,bootstrap_closed=state.closed)) if old else None,new=json.dumps(response),fingerprint=fingerprint,response=json.dumps(response)))
        return response


@storage_errors
def list_users(page,size,query=''):
    store=adapter()
    with store.engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'));store._verify(connection)
            state=inspect_setup(connection)
            if not state.users_ready:return dict(items=[public_user(bootstrap(),True)] if page==1 else [],total=1,page=page,page_size=size,storage_ready=False,is_demo=True)
            pattern='%'+query+'%'
            total=connection.execute(text('SELECT count(*) FROM v2_demo.users WHERE username ILIKE :query OR name ILIKE :query'),{'query':pattern}).scalar_one()
            rows=connection.execute(text('SELECT * FROM v2_demo.users WHERE username ILIKE :query OR name ILIKE :query ORDER BY username,id LIMIT :size OFFSET :offset'),dict(size=size,offset=(page-1)*size,query=pattern)).mappings()
            return dict(items=[public_user(row,True,bootstrap_closed=state.closed) for row in rows],total=total,page=page,page_size=size,storage_ready=True,is_demo=True)


@storage_errors
def audit_users(page,size):
    store=adapter()
    with store.engine.connect() as connection:
        store._verify(connection)
        if not ready(connection):return dict(items=[],total=0)
        total=connection.execute(text('SELECT count(*) FROM v2_demo.user_audit')).scalar_one()
        rows=connection.execute(text('SELECT id,actor_id,target_id,operation,previous_values,new_values,result,occurred_at FROM v2_demo.user_audit ORDER BY occurred_at DESC,id LIMIT :size OFFSET :offset'),dict(size=size,offset=(page-1)*size)).mappings()
        return dict(items=[dict(row) for row in rows],total=total)


def initialize_users():
    from app.demo_repair import preflight,ROOT,require
    store=adapter();preflight(store.engine)
    with store.engine.begin() as connection:
        store._verify(connection)
        require(Path(connection.execute(text('SHOW data_directory')).scalar_one()).resolve()==(ROOT/'.local/postgres-v2-demo').resolve(),'Bu repo V2 kümesi doğrulanamadı.')
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('v2-user-management'))"))
        initialized=connection.execute(text("SELECT to_jsonb(s)->>'identity_initialized' FROM v2_demo.schema_state s WHERE version=1")).scalar_one()
        require(initialized!='true' or ready(connection),'Kimlik deposu eksik; hesaplar yeniden oluşturulmadı.')
        for statement in (ROOT/'migrations/versions/004_demo_identity.sql').read_text().split(';'):
            if statement.strip():connection.execute(text(statement))
        if initialized!='true':
            user=bootstrap()
            connection.execute(text('''INSERT INTO v2_demo.users(id,username,name,email,role,active,password_hash,permissions,revision)
             VALUES (:id,:username,:name,:email,:role,:active,:password_hash,CAST(:permissions AS jsonb),:revision) ON CONFLICT DO NOTHING'''),{**user,'permissions':json.dumps(user['permissions'])})
        candidates=connection.execute(text("SELECT permissions FROM v2_demo.users WHERE role='ADMIN' AND active")).scalars()
        require(any(all(grants.get(r['id'],{}).get('can_view') is True for r in ROUTERS) for grants in candidates),'Tam yönetim kapsamlı aktif ADMIN bulunamadı; mevcut hesaplar sıfırlanmadı.')


@storage_errors
def record_rejection(payload,actor_id,target_id,operation,error):
    """Record a validated failed management command after its transaction rolled back."""
    store=adapter();attempt=payload.model_dump(exclude={'password'})
    with store.engine.begin() as connection:
        store._verify(connection)
        state=inspect_setup(connection)
        if not state.users_ready:return
        old=connection.execute(text('SELECT * FROM v2_demo.users WHERE id=:id'),{'id':target_id}).mappings().one_or_none() if target_id else None
        connection.execute(text("""INSERT INTO v2_demo.user_audit(id,actor_id,target_id,operation,previous_values,new_values,result,fingerprint,response)
          VALUES (:id,:actor,:target,:operation,CAST(:previous AS jsonb),CAST(:new AS jsonb),'REJECTED',:fingerprint,CAST(:response AS jsonb)) ON CONFLICT (id) DO NOTHING"""),
          dict(id=payload.request_id,actor=actor_id,target=target_id or 'new:'+getattr(payload,'username',''),operation=operation,
               previous=json.dumps(public_user(old,True,bootstrap_closed=state.closed)) if old else None,new=json.dumps(attempt),fingerprint=json.dumps(attempt,sort_keys=True),response=json.dumps({'detail':error.detail,'status':error.status_code})))
