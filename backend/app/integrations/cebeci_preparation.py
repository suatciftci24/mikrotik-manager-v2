"""Single-candidate planning and pure synthetic comparison. No transport or connection config."""
from datetime import datetime,timedelta,timezone
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator
from fastapi import HTTPException
from app.core.security import current_admin

CANDIDATE='CEBECI_TOWERS'
# Descriptors only. These are never passed to a command runner or API client.
READ_FIELDS={
 '/system/identity':('name',),
 '/system/resource':('board-name','version','uptime','cpu-load','total-memory','free-memory'),
 '/interface':('.id','name','type','disabled','running'),
 '/ip/route':('.id','dst-address','gateway','distance','active','disabled'),
 '/ip/ipsec/active-peers':('state','ph2-total','last-seen'),
 '/ip/ipsec/installed-sa':('state','auth-algorithm','enc-algorithm','current-bytes'),
 '/ppp/secret':('.id','name','service','profile','disabled'),
 '/ppp/active':('.id','name','service','uptime'),
}
STOP_CODES=('WRONG_ROUTER_IDENTITY','MODEL_MISMATCH','VERSION_MISMATCH','ACCESS_ERROR','PERMISSION_MISMATCH','UNEXPECTED_WRITE_ATTEMPT','DATA_INCONSISTENCY','V1_IMPACT','TLS_UNVERIFIED','UNSUPPORTED_PATH_OR_FIELD','SENSITIVE_FIELD_RETURNED')
GATES=('EXPLICIT_SINGLE_DEVICE_APPROVAL','REGISTER_VERIFIED_ROUTER_AUTHORIZATION','READ_ONLY_ACCOUNT_REVIEW','MANAGEMENT_SOURCE_ALLOWLIST','TLS_CERTIFICATE_AND_CLIENT_REVIEW','ROS6_FIELD_LAB_VERIFICATION','TIMEBOX_AND_STOP_OWNER','V1_BASELINE_AND_ROLLBACK_REVIEW','SEPARATE_EXECUTION_AUTHORIZATION')

class Snapshot(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source:Literal['SYNTHETIC_FIXTURE']='SYNTHETIC_FIXTURE'
    candidate:Literal['CEBECI_TOWERS']='CEBECI_TOWERS'
    identity:str|None=None
    model:str|None=None
    version:str|None=None
    observed_at:datetime|None=None
    captured_at:datetime|None=None
    rows:dict[str,list[dict]]=Field(default_factory=dict,max_length=8,repr=False)
    @field_validator('observed_at','captured_at')
    @classmethod
    def aware(cls,value):
        if value and value.utcoffset() is None:raise ValueError('Aware synthetic clock required')
        return value.astimezone(timezone.utc) if value else None


def authorize(user,candidate=CANDIDATE,purpose='PLAN_VIEW'):
    current_admin(user)
    if candidate!=CANDIDATE:raise HTTPException(404,'Plan adayı bulunamadı')
    # No fake mapping to demo-router-001, no implication that existing grants cover this device.
    if purpose!='PLAN_VIEW':raise HTTPException(403,'Aday cihaz yetki kaydı ve yürütme onayı yok')


def validate_read_descriptor(menu,fields):
    if menu not in READ_FIELDS or not fields or len(fields)!=len(set(fields)) or set(fields)-set(READ_FIELDS[menu]):raise ValueError('Read descriptor outside approved planning scope')
    return tuple(fields)


def project_fixture_row(menu,row):
    if menu not in READ_FIELDS:raise ValueError('Unknown synthetic menu')
    # API .proplist may still return extra fields: receiver projection is mandatory.
    result={}
    for key in READ_FIELDS[menu]:
        if key not in row:continue
        value=row[key]
        if value is not None and type(value) not in (str,int,float,bool):continue
        if isinstance(value,str) and any(marker in value.lower() for marker in ('secretref:','password=','token=','://')):continue
        if key in ('active','disabled','running') and not (type(value) is bool or isinstance(value,str) and value.lower() in ('true','false','yes','no')):continue
        if key in ('cpu-load','total-memory','free-memory','distance','ph2-total','current-bytes') and not (type(value) is int and value>=0 or isinstance(value,str) and value.isascii() and value.isdigit()):continue
        if key not in ('active','disabled','running','cpu-load','total-memory','free-memory','distance','ph2-total','current-bytes') and value is not None and not isinstance(value,str):continue
        result[key]=value
    return result


def compare(value:Snapshot,now:datetime):
    snapshot=Snapshot.model_validate(value.model_dump(mode='json'))
    if now.utcoffset() is None:raise ValueError('Aware comparison clock required')
    stops=[];unknown=[];warnings=[]
    for key,expected,code in [('identity',CANDIDATE,'WRONG_ROUTER_IDENTITY'),('model','RB3011UiAS','MODEL_MISMATCH'),('version','6.49.19','VERSION_MISMATCH')]:
        seen=getattr(snapshot,key)
        if seen is None:unknown.append(key.upper()+'_UNKNOWN')
        elif seen!=expected:stops.append(code)
    if snapshot.observed_at is None or snapshot.captured_at is None:unknown.append('OBSERVATION_TIME_UNKNOWN')
    elif snapshot.observed_at>snapshot.captured_at or snapshot.captured_at>now:unknown.append('CLOCK_SKEW_UNKNOWN')
    elif now-snapshot.observed_at>timedelta(minutes=5):warnings.append('STALE_SYNTHETIC_OBSERVATION')
    elif snapshot.observed_at!=snapshot.captured_at:warnings.append('DIFFERENT_SOURCE_CAPTURE_TIMES')
    identity_rows=snapshot.rows.get('/system/identity',[])
    if len(identity_rows)>1:stops.append('ROUTER_IDENTITY_COLLISION')
    for row in identity_rows:
        seen=project_fixture_row('/system/identity',row).get('name')
        if seen is not None and seen!=CANDIDATE:stops.append('WRONG_ROUTER_IDENTITY')
    for row in snapshot.rows.get('/system/resource',[]):
        safe=project_fixture_row('/system/resource',row)
        if safe.get('board-name') is not None and safe['board-name']!='RB3011UiAS':stops.append('MODEL_MISMATCH')
        if safe.get('version') is not None and safe['version']!='6.49.19':stops.append('VERSION_MISMATCH')
    missing={};counts={}
    for menu,fields in READ_FIELDS.items():
        rows=snapshot.rows.get(menu)
        if rows is None:unknown.append('PATH_UNMEASURED:'+menu);missing[menu]=list(fields);counts[menu]=None;continue
        for row in rows:
            projected=project_fixture_row(menu,row)
            if any(key in row for key in ('password','auth-key','enc-key','secret','psk','private-key','api-key')):stops.append('SENSITIVE_FIELD_RETURNED')
            if any(key in row and row[key] is not None and key not in projected for key in fields):stops.append('DATA_INCONSISTENCY')
        counts[menu]=len(rows);missing[menu]=list(fields) if not rows else sorted({field for row in rows for field in fields if field not in project_fixture_row(menu,row) or project_fixture_row(menu,row)[field] is None})
        if missing[menu]:warnings.append('FIELDS_MISSING:'+menu)
        # Empty peers/routes/accounts are not evidence of an outage or absent subscriber authority.
        if not rows:unknown.append('EMPTY_SOURCE:'+menu)
    if set(snapshot.rows)-set(READ_FIELDS):stops.append('UNSUPPORTED_PATH_OR_FIELD')
    accounts=[project_fixture_row('/ppp/secret',row) for row in snapshot.rows.get('/ppp/secret',[])]
    names=[row.get('name') for row in accounts if isinstance(row.get('name'),str) and row.get('name')]
    if len(names)!=len(set(names)):stops.append('ACCOUNT_IDENTITY_COLLISION')
    for menu,code in [('/ppp/secret','ACCOUNT_SOURCE_ID_COLLISION'),('/ppp/active','SESSION_IDENTITY_COLLISION')]:
        ids=[row.get('.id') for row in (project_fixture_row(menu,r) for r in snapshot.rows.get(menu,[])) if isinstance(row.get('.id'),str)]
        if len(ids)!=len(set(ids)):stops.append(code)
    return dict(source='SYNTHETIC_FIXTURE',result='STOP' if stops else 'UNKNOWN' if unknown else 'WARNING' if warnings else 'SYNTHETIC_MATCH',stop_codes=sorted(set(stops)),unknown=sorted(set(unknown)),warnings=sorted(set(warnings)),missing_fields=missing,row_counts=counts,live_identity_verified=False,wan_status='UNKNOWN',ipsec_status='UNKNOWN',pppoe_backend='UNKNOWN',execution_authorized=False)


def profile(user,candidate=CANDIDATE):
    authorize(user,candidate)
    from app.integrations.cebeci_access import assess
    access_preparation=assess(user)
    at=datetime(2026,10,28,12,tzinfo=timezone.utc)
    # Deliberately incomplete synthetic rows: no real device observation or current health claim.
    fixture=Snapshot(identity=CANDIDATE,model='RB3011UiAS',version='6.49.19',observed_at=at,captured_at=at,rows={'/system/identity':[{'name':CANDIDATE}],'/system/resource':[{'board-name':'RB3011UiAS','version':'6.49.19'}],'/ppp/secret':[{'name':'synthetic-user-cebeci','service':'pppoe','profile':'fixture-profile-basic','disabled':False}]})
    return dict(access_preparation=access_preparation,candidate_id=CANDIDATE,mode='SYNTHETIC / PLANNING',connection='NOT CONNECTED',history_label='HISTORICAL DATA',approval='APPROVAL REQUIRED',execution_authorized=False,routeros_enabled=False,radius_enabled=False,automatic_retry=False,polling=False,
        historical=dict(identity=CANDIDATE,model='RB3011UiAS',version='6.49.19',management_address='10.250.0.19',ipsec_center_address='10.250.0.1',source='USER_PROVIDED_HISTORICAL',verified_at=None),
        authorization=dict(binding='UNASSIGNED',device_access='NOT_GRANTED',plan_view='FULL_SCOPE_ADMIN_ONLY',required_permissions=['can_view','can_view_reports'],note='Aday envantere veya demo router izinlerine bağlanmadı; mevcut ADMIN rolü cihaz erişimi vermez.'),
        read_scope=[dict(menu=menu,properties=list(fields),compatibility='ROS6_LAB_VERIFICATION_REQUIRED') for menu,fields in READ_FIELDS.items()],
        security=dict(proposed_policies=['read','api'],forbidden_policies=['write','policy','test','sensitive','reboot','ftp','password','ssh','winbox','telnet','local','web','sniff','romon'],tls='UNKNOWN_REQUIRES_VERIFIED_API_SSL',plain_api='BLOCKED',rest_api='NOT_A_ROUTEROS6_FALLBACK',source_allowlist='UNVERIFIED_NO_CURRENT_ADDRESS',secret_storage='NONE',note='Varsayılan read grubu minimum değildir. read/api yalnız aday politika; 6.49.19 üzerinde alan ve dosya erişimi sınırları ayrıca doğrulanmalı.'),
        unknown_requirements=['CURRENT_IDENTITY_MODEL_VERSION','CURRENT_MANAGEMENT_PATH','IPSEC_HEALTH','API_SSL_CERTIFICATE_AND_TLS','READ_ACCOUNT_POLICY_BEHAVIOR','CENTRAL_SOURCE_AFTER_ROUTING_NAT','ROS6_PROPERTY_AVAILABILITY','SOURCE_TIME_AND_BACKEND_AUTHORITY'],
        risks=[dict(severity='P1',code='LIVE_IDENTITY_AND_AUTHORIZATION_UNVERIFIED'),dict(severity='P1',code='TLS_CERTIFICATE_AND_CLIENT_UNVERIFIED'),dict(severity='P1',code='PPP_AND_SA_SENSITIVE_FIELD_EXPOSURE'),dict(severity='P2',code='ROS6_BUILD_PROPERTY_SUPPORT_UNTESTED'),dict(severity='P2',code='HISTORICAL_ADDRESSES_NOT_CURRENT_PATH'),dict(severity='P2',code='V1_IMPACT_NOT_MEASURED')],gates=list(GATES),stop_conditions=list(STOP_CODES),rollback_executable=False,comparison=compare(fixture,at),comparison_clock='DETERMINISTIC_SYNTHETIC_CLOCK_NOT_CURRENT_OBSERVATION',is_demo=True)
