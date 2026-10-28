"""Offline synthetic mapping review only. No V1 imports, credentials, IO or activation."""
from collections import Counter
from hashlib import sha256
import re
from datetime import date,datetime,timezone
from enum import StrEnum
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator
from fastapi import HTTPException
from app.core.authorization import routers_for,require_router
from app.integrations.contracts import Backend,ExternalConfiguration
from app.services.demo_data import ROUTERS

class Preparation(StrEnum):
    DEMO_ONLY='DEMO_ONLY'
    READY_FOR_REVIEW='READY_FOR_REVIEW'
    APPROVAL_REQUIRED='APPROVAL_REQUIRED'
    BLOCKED='BLOCKED'
class Fixture(BaseModel):model_config=ConfigDict(extra='forbid',frozen=True)
class RouterMapping(Fixture):
    legacy_key:str=Field(pattern=r'^fixture-router-[a-z0-9-]+$')
    target_id:str
    management_identity:str|None=Field(default=None,pattern=r'^fixture-management-[a-z0-9-]+$')
class AccountMapping(Fixture):
    legacy_key:str=Field(pattern=r'^fixture-account-[a-z0-9-]+$')
    target_key:str=Field(pattern=r'^planned-account-[a-z0-9-]+$')
    legacy_router:str
    username:str|None=Field(default=None,pattern=r'^synthetic-user-[a-z0-9-]+$')
    backend:Backend|None=None
    target_backend:Backend|None=None
    legacy_profile:str|None=Field(default=None,pattern=r'^fixture-profile-[a-z0-9-]+$')
    target_profile:str|None=Field(default=None,pattern=r'^planned-profile-[a-z0-9-]+$')
    expiry_mode:Literal['DATE','UNLIMITED','UNKNOWN']='UNKNOWN'
    expires_on:date|None=None
    @field_validator('expires_on',mode='before')
    @classmethod
    def explicit_calendar_day(cls,value):
        if value is not None and not (type(value) is date or isinstance(value,str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value)):raise ValueError('Explicit synthetic calendar day required')
        return value
class SessionMapping(Fixture):
    legacy_key:str=Field(pattern=r'^fixture-session-[a-z0-9-]+$')
    account_key:str
    started_at:datetime|None=None
    ended_at:datetime|None=None
    @field_validator('started_at','ended_at')
    @classmethod
    def aware(cls,value):
        if value and value.utcoffset() is None:raise ValueError('Aware fixture time required')
        return value
class AuditMapping(Fixture):
    legacy_key:str=Field(pattern=r'^fixture-audit-[a-z0-9-]+$')
    account_key:str
    actor_key:str|None=Field(default=None,pattern=r'^fixture-actor-[a-z0-9-]+$')
    occurred_at:datetime|None=None
    result:Literal['SUCCESS','REJECTED','UNKNOWN']='UNKNOWN'
    @field_validator('occurred_at')
    @classmethod
    def aware(cls,value):return SessionMapping.aware(value)
class MappingSet(Fixture):
    source:Literal['SYNTHETIC_FIXTURE']='SYNTHETIC_FIXTURE'
    routers:tuple[RouterMapping,...]=Field(default=(),max_length=100)
    accounts:tuple[AccountMapping,...]=Field(default=(),max_length=100)
    sessions:tuple[SessionMapping,...]=Field(default=(),max_length=100)
    audits:tuple[AuditMapping,...]=Field(default=(),max_length=100)

FIELD_RULES=(
 ('router.identity','router.id','Açık, bire bir eşleme; IP/ad benzerliğinden kimlik çıkarma yok.'),
 ('router.management_identity','management_identity_plan','Yalnız sentetik opaque kimlik; adres/login/sır alınmaz.'),
 ('pppoe.account_id + router.identity','account_mapping_key','Router kapsamında tekil kaynak/target; username tek başına kimlik değildir.'),
 ('pppoe.backend','source LOCAL/RADIUS','Tek otorite; uyumsuzluk BLOCKED, otomatik dönüşüm yok.'),
 ('pppoe.profile','profile_mapping_key','Açık profil eşleme; cihaz profili oluşturma yok.'),
 ('pppoe.expire','expires_on + expiry_mode','DATE/UNLIMITED/UNKNOWN ayrı; tarih Europe/Istanbul takvim günüdür.'),
 ('session.id + account_id','session_lineage','Başlangıç/bitiş UTC; eksik zaman UNKNOWN, süre uydurulmaz.'),
 ('audit.id + actor + time + result','audit_lineage','Orijinal kimlik ve aktör anlamı korunur; canlı audit aktarımı/yeniden yazması yok.'),
)
PILOT_GATES=('EXPLICIT_ADMIN_SCOPE','ONE_ROUTER_ONLY','READ_ONLY_ACCESS','TIMEBOX_AND_STOP_OWNER','SECRET_STORE_REVIEW','IDENTITY_MAPPING_REVIEW','ROLLBACK_REHEARSAL','SEPARATE_EXECUTION_AUTHORIZATION')


def validate_mapping(value:MappingSet):
    data=MappingSet.model_validate(value.model_dump(mode='json'));issues=set()
    def duplicates(values,code):
        if any(n>1 for n in Counter(values).values()):issues.add(code)
    duplicates((r.legacy_key for r in data.routers),'ROUTER_SOURCE_COLLISION')
    duplicates((r.target_id for r in data.routers),'ROUTER_TARGET_COLLISION')
    duplicates((r.management_identity for r in data.routers if r.management_identity),'MANAGEMENT_IDENTITY_COLLISION')
    duplicates((a.legacy_key for a in data.accounts),'ACCOUNT_SOURCE_COLLISION')
    duplicates((a.target_key for a in data.accounts),'ACCOUNT_TARGET_COLLISION')
    duplicates(((a.legacy_router,a.username) for a in data.accounts if a.username),'ACCOUNT_USERNAME_COLLISION')
    duplicates((s.legacy_key for s in data.sessions),'SESSION_ID_COLLISION')
    duplicates((a.legacy_key for a in data.audits),'AUDIT_ID_COLLISION')
    routers={r.legacy_key:r for r in data.routers};accounts={a.legacy_key:a for a in data.accounts}
    if not data.routers:issues.add('ROUTER_MAPPING_MISSING')
    for row in data.routers:
        if row.target_id not in {r['id'] for r in ROUTERS}:issues.add('ROUTER_TARGET_UNKNOWN')
        if not row.management_identity:issues.add('MANAGEMENT_IDENTITY_MISSING')
    for row in data.accounts:
        if row.legacy_router not in routers:issues.add('ACCOUNT_ROUTER_MISSING')
        if not row.username:issues.add('USERNAME_MISSING')
        if not row.backend or not row.target_backend:issues.add('BACKEND_MISSING')
        elif row.backend!=row.target_backend:issues.add('BACKEND_MISMATCH')
        if not row.legacy_profile or not row.target_profile:issues.add('PROFILE_MAPPING_MISSING')
        if row.expiry_mode=='UNKNOWN' or row.expiry_mode=='DATE' and row.expires_on is None:issues.add('EXPIRY_DECISION_MISSING')
        if row.expiry_mode=='UNLIMITED' and row.expires_on is not None:issues.add('EXPIRY_CONFLICT')
    for row in data.sessions:
        if row.account_key not in accounts:issues.add('SESSION_ACCOUNT_MISSING')
        if row.ended_at and (not row.started_at or row.ended_at<row.started_at):issues.add('SESSION_INTERVAL_INVALID')
    for row in data.audits:
        if row.account_key not in accounts:issues.add('AUDIT_ACCOUNT_MISSING')
        if not row.actor_key or not row.occurred_at or row.result=='UNKNOWN':issues.add('AUDIT_LINEAGE_INCOMPLETE')
    return dict(fixture_digest=sha256(data.model_dump_json().encode()).hexdigest(),result='BLOCKED' if issues else 'VALIDATED_SYNTHETIC',issues=sorted(issues),counts={name:len(getattr(data,name)) for name in ('routers','accounts','sessions','audits')},unknown_session_times=sum(not s.started_at or not s.ended_at for s in data.sessions))


def fixture_for(router_id):
    """Server-owned synthetic fixtures; never reads V1/V2 business records."""
    index=next(i for i,r in enumerate(ROUTERS) if r['id']==router_id)
    router=RouterMapping(legacy_key=f'fixture-router-{index}',target_id=router_id,management_identity=f'fixture-management-{index}')
    account=AccountMapping(legacy_key=f'fixture-account-{index}',target_key=f'planned-account-{index}',legacy_router=router.legacy_key,username=f'synthetic-user-{index}',backend='LOCAL',target_backend='LOCAL',legacy_profile='fixture-profile-basic',target_profile='planned-profile-basic',expiry_mode='UNLIMITED')
    if index==1:account=account.model_copy(update={'target_backend':Backend.RADIUS,'target_profile':None})
    if index==2:return None,False
    return MappingSet(routers=(router,),accounts=(account,),sessions=(SessionMapping(legacy_key=f'fixture-session-{index}',account_key=account.legacy_key),),audits=(AuditMapping(legacy_key=f'fixture-audit-{index}',account_key=account.legacy_key,actor_key='fixture-actor-review',occurred_at=datetime(2026,10,28,12,tzinfo=timezone.utc),result='SUCCESS'),)),index==3


def plan_row(router):
    review_complete=False
    try:
        fixture,review_complete=fixture_for(router['id'])
        if fixture is None:mapping=dict(result='NOT_EVALUATED',issues=[],counts=dict(routers=0,accounts=0,sessions=0,audits=0),unknown_session_times=0);state=Preparation.DEMO_ONLY
        else:
            mapping=validate_mapping(fixture)
            state=Preparation.BLOCKED if mapping['issues'] else Preparation.APPROVAL_REQUIRED if review_complete else Preparation.READY_FOR_REVIEW
    except ValueError:
        mapping=dict(result='BLOCKED',issues=['MAPPING_FIXTURE_INVALID'],counts=dict(routers=0,accounts=0,sessions=0,audits=0),unknown_session_times=0);state=Preparation.BLOCKED;review_complete=False
    config=ExternalConfiguration()
    return dict(router_id=router['id'],name=router['name'],preparation=state.value,mode='DEMO / SYNTHETIC',connection='NOT CONNECTED',mapping=mapping,missing_requirements=list(PILOT_GATES),pilot_approval_required=True,execution_authorized=False,synthetic_review_complete=review_complete,external_writes=config.external_writes,routeros_enabled=config.routeros_enabled,radius_enabled=config.radius_enabled)


def inventory(user,router_id='',page=1,page_size=10):
    if not 1<=page<=1000000 or not 1<=page_size<=25:raise HTTPException(422,'Geçerli sayfa gerekli')
    if router_id:require_router(user,router_id,'can_view_reports')
    rows=[plan_row(router) for router in routers_for(user,'can_view_reports') if not router_id or router['id']==router_id]
    return dict(items=rows[(page-1)*page_size:page*page_size],total=len(rows),page=page,page_size=page_size,is_demo=True,read_only=True,connection='NOT CONNECTED',execution_authorized=False)


def detail(user,router_id):
    require_router(user,router_id,'can_view_reports')
    router=next(r for r in ROUTERS if r['id']==router_id)
    return dict(item=plan_row(router),field_rules=[dict(source=a,target=b,rule=c) for a,b,c in FIELD_RULES],pilot_gates=list(PILOT_GATES),rollback_triggers=['CONNECTION_LOSS','ACCESS_DENIED','DATA_INCONSISTENCY','IDENTITY_MISMATCH'],rollback_steps=['STOP_PILOT_READS','KEEP_ADAPTERS_DISABLED','PRESERVE_REDACTED_EVIDENCE','QUARANTINE_NEW_PILOT_NAMESPACE','VERIFY_PRE_PILOT_BASELINE','REQUIRE_FRESH_REVIEW'],rollback_executable=False,is_demo=True)
