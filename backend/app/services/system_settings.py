"""Whitelisted presentation preferences only. Runtime security and adapters are immutable."""
import json
from typing import Literal
from uuid import UUID,uuid4
from pydantic import BaseModel,ConfigDict,Field,field_validator
from sqlalchemy import text
from app.adapters.demo_subscriptions import storage_errors
from app.services import identity
from app.services.demo_subscriptions import DemoChangeError,DemoStorageUnavailable

class Values(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    app_name:str=Field(default='MikroTik Manager V2',min_length=1,max_length=80)
    timezone:Literal['Europe/Istanbul']='Europe/Istanbul'
    page_size:Literal[10,25,50]=25
    theme:Literal['system','light','dark']='system'
    notifications_enabled:bool=True
    notification_levels:list[Literal['P1','P2','P3','P4']]=Field(default_factory=lambda:['P1','P2','P3','P4'],max_length=4)
    @field_validator('app_name')
    @classmethod
    def meaningful(cls,value):
        if not value.strip() or any(ord(c)<32 for c in value):raise ValueError('Geçerli uygulama adı gerekli')
        return value.strip()
    @field_validator('notification_levels')
    @classmethod
    def unique(cls,value):
        if len(value)!=len(set(value)):raise ValueError('Tekrarlanan önem seviyesi')
        return sorted(value)

class Personal(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    theme:Literal['system','light','dark']|None=None
    page_size:Literal[10,25,50]|None=None
    notifications_enabled:bool|None=None
    notification_levels:list[Literal['P1','P2','P3','P4']]|None=Field(default=None,max_length=4)
    @field_validator('notification_levels')
    @classmethod
    def unique(cls,value):return Values.unique(value) if value is not None else None

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:UUID
    expected_revision:int=Field(ge=0)
    confirmed:Literal[True]
    values:Values

class PersonalCommand(Command):
    values:Personal


def profile_id(value):
    if value=='default':return value
    if value.startswith('demo-settings-'):
        try:return 'demo-settings-'+str(UUID(value.removeprefix('demo-settings-')))
        except ValueError:pass
    raise DemoChangeError(404,'Ayar profili bulunamadı')


def ready(connection):
    return bool(connection.execute(text("SELECT to_regclass('v2_demo.settings_records') IS NOT NULL AND to_regclass('v2_demo.settings_audit') IS NOT NULL")).scalar_one())


def clean(id,values):return (Personal if id.startswith('user:') else Values).model_validate(values).model_dump()


def record(connection,id):
    row=connection.execute(text('SELECT * FROM v2_demo.settings_records WHERE id=:id'),{'id':id}).mappings().one_or_none()
    if row:return dict(record_id=id,values=clean(id,row['payload']),revision=row['revision'],updated_at=row['updated_at'].isoformat() if row['updated_at'] else None,storage_ready=True,is_demo=True)
    if id.startswith('user:'):return dict(record_id=id,values=Personal().model_dump(),revision=0,updated_at=None,storage_ready=True,is_demo=True)
    if id=='default':raise DemoStorageUnavailable()
    raise DemoChangeError(404,'Ayar profili bulunamadı')


@storage_errors
def load(id='default'):
    store=identity.adapter()
    with store.engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'));store._verify(connection)
            if not ready(connection):
                if id!='default' and not id.startswith('user:'):raise DemoChangeError(404,'Ayar profili bulunamadı')
                return dict(record_id=id,values=(Personal() if id.startswith('user:') else Values()).model_dump(),revision=0,updated_at=None,storage_ready=False,is_demo=True)
            return record(connection,id)


@storage_errors
def effective(user_id):
    # One coherent read snapshot for defaults and personal overrides.
    store=identity.adapter()
    with store.engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'));store._verify(connection)
            if not ready(connection):return dict(values=Values().model_dump(),personal=Personal().model_dump(),revision=0,storage_ready=False,is_demo=True)
            defaults=record(connection,'default');personal=record(connection,'user:'+user_id)
            return dict(values={**defaults['values'],**{k:v for k,v in personal['values'].items() if v is not None}},personal=personal['values'],revision=personal['revision'],storage_ready=True,is_demo=True)


def actor_allowed(actor,personal):
    return bool(actor and actor['active'] and (personal or identity.public_user(actor)['can_manage_users']))


@storage_errors
def save(id,payload,actor_id,personal=False):
    if personal:
        if id!='user:'+actor_id:raise DemoChangeError(403,'Yalnız kendi tercihlerinizi değiştirebilirsiniz')
    else:id=profile_id(id)
    store=identity.adapter();fingerprint=json.dumps([id,actor_id,payload.model_dump(mode='json')],sort_keys=True)
    with store.engine.begin() as connection:
        store._verify(connection)
        if not ready(connection):raise DemoChangeError(503,'Ayar deposu hazır değil; açık settings-init bakımı gerekli.')
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('v2-settings'))"))
        actor=connection.execute(text('SELECT * FROM v2_demo.users WHERE id=:id FOR SHARE'),{'id':actor_id}).mappings().one_or_none()
        if not actor_allowed(actor,personal):raise DemoChangeError(403,'Ayar değişikliği yetkisi gerekli')
        receipt=connection.execute(text('SELECT * FROM v2_demo.settings_audit WHERE id=:id'),{'id':str(payload.request_id)}).mappings().one_or_none()
        if receipt:
            if receipt['fingerprint']!=fingerprint:raise DemoChangeError(409,'İstek kimliği farklı ayar işlemi için kullanılmış.')
            if receipt['result']!='SUCCESS':raise DemoChangeError(receipt['response']['status'],receipt['response']['detail'])
            return receipt['response']
        old=record(connection,id)
        if old['revision']!=payload.expected_revision:raise DemoChangeError(409,'Ayarlar değişmiş; yeniden yükleyin.')
        values=payload.values.model_dump()
        row=connection.execute(text('''INSERT INTO v2_demo.settings_records(id,payload,revision) VALUES (:id,CAST(:values AS jsonb),1)
          ON CONFLICT(id) DO UPDATE SET payload=EXCLUDED.payload,revision=settings_records.revision+1,updated_at=now() RETURNING *'''),dict(id=id,values=json.dumps(values))).mappings().one()
        result=dict(record_id=id,values=values,revision=row['revision'],updated_at=row['updated_at'].isoformat(),storage_ready=True,is_demo=True)
        connection.execute(text('''INSERT INTO v2_demo.settings_audit(id,record_id,actor_id,previous_values,new_values,result,fingerprint,response)
          VALUES (:id,:record,:actor,CAST(:previous AS jsonb),CAST(:new AS jsonb),'SUCCESS',:fingerprint,CAST(:response AS jsonb))'''),
          dict(id=str(payload.request_id),record=id,actor=actor_id,previous=json.dumps(old['values']),new=json.dumps(values),fingerprint=fingerprint,response=json.dumps(result)))
        return result


@storage_errors
def rejected(id,payload,actor_id,error):
    store=identity.adapter()
    with store.engine.begin() as connection:
        store._verify(connection)
        if not ready(connection):return
        try:old=record(connection,id)
        except DemoChangeError:return
        connection.execute(text('''INSERT INTO v2_demo.settings_audit(id,record_id,actor_id,previous_values,new_values,result,fingerprint,response)
          VALUES (:id,:record,:actor,CAST(:previous AS jsonb),CAST(:new AS jsonb),'REJECTED',:fingerprint,CAST(:response AS jsonb)) ON CONFLICT(id) DO NOTHING'''),
          dict(id=str(payload.request_id),record=id,actor=actor_id,previous=json.dumps(old['values']),new=json.dumps(payload.values.model_dump()),fingerprint=json.dumps([id,actor_id,payload.model_dump(mode='json')],sort_keys=True),response=json.dumps(dict(status=error.status_code,detail=error.detail))))


@storage_errors
def audit(id,page,size):
    store=identity.adapter()
    with store.engine.connect() as connection:
        store._verify(connection)
        if not ready(connection):return dict(items=[],total=0,page=page,page_size=size)
        total=connection.execute(text('SELECT count(*) FROM v2_demo.settings_audit WHERE record_id=:record'),{'record':id}).scalar_one()
        rows=connection.execute(text('SELECT id,record_id,actor_id,previous_values,new_values,result,occurred_at FROM v2_demo.settings_audit WHERE record_id=:record ORDER BY occurred_at DESC,id LIMIT :size OFFSET :offset'),dict(record=id,size=size,offset=(page-1)*size)).mappings()
        return dict(items=[dict(row) for row in rows],total=total,page=page,page_size=size)


def initialize():
    from app.demo_repair import preflight,ROOT,require
    from pathlib import Path
    store=identity.adapter();preflight(store.engine)
    with store.engine.begin() as connection:
        store._verify(connection)
        require(Path(connection.execute(text('SHOW data_directory')).scalar_one()).resolve()==(ROOT/'.local/postgres-v2-demo').resolve(),'Bu repo V2 kümesi doğrulanamadı.')
        require(identity.ready(connection),'Önce mevcut kullanıcı deposu hazır olmalı; kullanıcılar değiştirilmedi.')
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('v2-settings'))"))
        initialized=connection.execute(text("SELECT to_jsonb(s)->>'settings_initialized' FROM v2_demo.schema_state s WHERE version=1")).scalar_one()
        require(initialized!='true' or ready(connection),'Kurulmuş ayar deposu eksik; varsayılanlar yeniden oluşturulmadı.')
        # Full-line SQL comments can contain semicolons; they are not statements.
        sql='\n'.join(line for line in (ROOT/'migrations/versions/005_demo_settings.sql').read_text().splitlines() if not line.lstrip().startswith('--'))
        for statement in sql.split(';'):
            if statement.strip():connection.execute(text(statement))
        if initialized!='true':connection.execute(text("INSERT INTO v2_demo.settings_records(id,payload) VALUES ('default',CAST(:values AS jsonb)) ON CONFLICT DO NOTHING"),{'values':Values().model_dump_json()})
        record(connection,'default')


def prepare_acceptance():
    initialize();store=identity.adapter();id='demo-settings-'+str(uuid4())
    with store.engine.begin() as connection:
        store._verify(connection)
        values=record(connection,'default')['values']
        connection.execute(text('INSERT INTO v2_demo.settings_records(id,payload) VALUES (:id,CAST(:values AS jsonb))'),dict(id=id,values=json.dumps(values)))
    return id
