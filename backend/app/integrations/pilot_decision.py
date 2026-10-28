"""Read-only deterministic review decisions. Never grants GO or execution authority."""
from hashlib import sha256
import json
from fastapi import HTTPException
from app.core.authorization import require_router,routers_for
from app.integrations import planning
from app.simulation.report import read_report

POLICY='synthetic-pilot-review-v1'
DOMAINS=(
 ('ROUTER_IDENTITY','Router kimliği',('ROUTER_','MANAGEMENT_')),
 ('PPPOE_ACCOUNT','PPPoE abone',('ACCOUNT_','USERNAME_','BACKEND_')),
 ('PROFILE','Profil',('PROFILE_',)),('EXPIRE','EXPIRE',('EXPIRY_',)),
 ('SESSION','Oturum',('SESSION_',)),('AUDIT','Audit lineage',('AUDIT_',)),
)
GATES=(('ADMIN_APPROVAL','Açık yönetici onayı','BLOCKED','APPROVAL_ABSENT'),('PILOT_SCOPE','Tek-router pilot kapsamı','UNKNOWN','SIGNED_SCOPE_UNMEASURED'),('TIMEBOX','Süre ve durdurma sorumlusu','UNKNOWN','TIMEBOX_UNMEASURED'),('ACCESS_LIMIT','Salt okunur cihaz erişim sınırı','UNKNOWN','DEVICE_RIGHTS_UNMEASURED'),('ROLLBACK_REHEARSAL','Hedefe özgü rollback provası','UNKNOWN','REHEARSAL_UNMEASURED'))


def _comparison(mapping):
    issues=mapping.get('issues',[]);result=mapping.get('result');counts=mapping.get('counts',{})
    rows=[]
    for id,label,prefixes in DOMAINS:
        relevant=sorted(code for code in issues if code.startswith(prefixes) or code=='MAPPING_FIXTURE_INVALID')
        count_key={'ROUTER_IDENTITY':'routers','PPPOE_ACCOUNT':'accounts','PROFILE':'accounts','EXPIRE':'accounts','SESSION':'sessions','AUDIT':'audits'}[id]
        status='BLOCKED' if relevant else 'UNKNOWN' if result not in ('VALIDATED_SYNTHETIC','BLOCKED') or not counts.get(count_key) else 'WARNING' if id=='SESSION' and mapping.get('unknown_session_times',0) else 'PASS'
        rows.append(dict(id=id,label=label,status=status,source='STAGE19_SYNTHETIC_MAPPING',reasons=relevant or (['SESSION_TIME_UNKNOWN'] if status=='WARNING' else ['NO_DOMAIN_EVIDENCE'] if status=='UNKNOWN' else ['SYNTHETIC_FIELDS_VALIDATED'])))
    return rows


def _evaluate(detail,simulation):
    row=detail['item'];comparison=_comparison(row['mapping']);criteria=[]
    def add(id,label,status,source,code):criteria.append(dict(id=id,label=label,status=status,source=source,reason=code))
    identity=next(c for c in comparison if c['id']=='ROUTER_IDENTITY')
    add('IDENTITY_MAPPING','Sentetik kimlik eşleştirmesi',identity['status'],'STAGE19_SYNTHETIC_MAPPING',identity['reasons'][0])
    add('REQUEST_AUTHORIZATION','Mevcut V2 isteğinin router yetkisi','PASS','CURRENT_REQUEST_AUTHORIZATION','ROUTER_REPORT_SCOPE_VERIFIED')
    add('SOURCE_VALIDATION','Gerçek kaynak doğrulaması','UNKNOWN','NO_DEVICE_OBSERVATION','REAL_SOURCE_NOT_MEASURED')
    add('FRESHNESS','Gerçek kaynak güncelliği','UNKNOWN','NO_DEVICE_OBSERVATION','SOURCE_TIME_NOT_MEASURED')
    audit=next(c for c in comparison if c['id']=='AUDIT')
    add('AUDIT_MAPPING','Sentetik audit alanları',audit['status'],'STAGE19_SYNTHETIC_MAPPING',audit['reasons'][0])
    add('ROLLBACK_PLAN','Rollback planı tanımı','PASS' if detail.get('rollback_steps') and detail.get('rollback_executable') is False else 'UNKNOWN','STAGE19_PLAN_DEFINITION','PLAN_ONLY_NOT_REHEARSED')
    isolated=all(row.get(key) is False for key in ('execution_authorized','external_writes','routeros_enabled','radius_enabled')) and row.get('connection')=='NOT CONNECTED'
    add('ISOLATION','Uygulama yapılandırmasında dış bağlantı/yazma kapalı','PASS' if isolated else 'BLOCKED','DISABLED_ADAPTER_CONFIGURATION','EXTERNAL_EFFECTS_DISABLED' if isolated else 'ISOLATION_NOT_PROVEN')
    simulated=[r for r in simulation.get('items',[]) if r.get('owner_router_id')==row['router_id']]
    add('SIMULATOR','Kaydedilmiş sentetik simülasyon kanıtı','WARNING' if simulated else 'UNKNOWN','STAGE18_RECORDED_SIMULATION' if simulated else 'NO_RECORDED_SIMULATION','SIMULATED_CLOCK_NOT_DEVICE_EVIDENCE' if simulated else 'SIMULATION_EVIDENCE_MISSING')
    for id,label,status,code in GATES:add(id,label,status,'NO_EXECUTION_APPROVAL',code)
    risks=[]
    def risk(code,severity,criterion,source):risks.append(dict(code=code,severity=severity,criterion=criterion,source=source))
    for item in comparison:
        for code in item['reasons']:
            if item['status']=='BLOCKED':risk(code,'P1' if 'COLLISION' in code else 'P2',item['id'],item['source'])
            elif item['status'] in ('UNKNOWN','WARNING'):risk(code,'P3',item['id'],item['source'])
    for item in criteria:
        if item['status']!='PASS':risk(item['reason'],'P1' if item['id']=='ISOLATION' else 'P2' if item['status']=='BLOCKED' else 'P4' if item['id']=='SIMULATOR' and item['status']=='WARNING' else 'P3',item['id'],item['source'])
    if row['mapping'].get('result')=='BLOCKED' and not any(c['status']=='BLOCKED' for c in comparison):risk('MAPPING_UNCLASSIFIED_BLOCKER','P2','MAPPING','STAGE19_SYNTHETIC_MAPPING')
    unique={(r['code'],r['criterion']):r for r in risks};risks=sorted(unique.values(),key=lambda r:(r['severity'],r['code'],r['criterion']))
    if row['mapping'].get('result')=='BLOCKED' or any(c['status']=='BLOCKED' for c in comparison) or not isolated:decision='NO_GO';reason='MAPPING_OR_ISOLATION_BLOCKER'
    elif all(c['status'] in ('PASS','WARNING') for c in comparison) and row.get('synthetic_review_complete') is True:decision='ELIGIBLE_FOR_REVIEW';reason='SYNTHETIC_BUNDLE_ELIGIBLE_FOR_HUMAN_REVIEW_ONLY'
    else:decision='REVIEW_REQUIRED';reason='MAPPING_REVIEW_OR_EVIDENCE_INCOMPLETE'
    reasons=[reason]+sorted({c['reason'] for c in criteria if c['status']!='PASS'})
    result=dict(router_id=row['router_id'],name=row['name'],policy=POLICY,mapping_evidence_hash=row['mapping'].get('fixture_digest'),mode='DEMO / SYNTHETIC',connection='NOT CONNECTED' if isolated else 'UNKNOWN',approval='APPROVAL REQUIRED',decision=decision,decision_reasons=reasons,execution_authorized=False,external_writes=False,checklist=criteria,comparison=comparison,risks=risks,missing_evidence=[c['id'] for c in criteria if c['status'] in ('UNKNOWN','BLOCKED')],field_rules=detail['field_rules'],simulation_run=simulation.get('last_run') if simulated else None)
    result['evidence_hash']=sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result


def assessment(user,router_id,simulation=None):
    require_router(user,router_id,'can_view_reports')
    detail=planning.detail(user,router_id)
    if detail['item']['router_id']!=router_id:raise HTTPException(503,'Plan kaynak kapsamı doğrulanamadı')
    return _evaluate(detail,read_report(user,page_size=5) if simulation is None else simulation)


def inventory(user,router_id='',page=1,page_size=10):
    if not 1<=page<=1000000 or not 1<=page_size<=25:raise HTTPException(422,'Geçerli sayfa gerekli')
    if router_id:require_router(user,router_id,'can_view_reports')
    routers=[r for r in routers_for(user,'can_view_reports') if not router_id or r['id']==router_id]
    simulation=read_report(user,page_size=5) if routers else {}
    rows=[assessment(user,r['id'],simulation) for r in routers[(page-1)*page_size:page*page_size]]
    return dict(items=rows,total=len(routers),page=page,page_size=page_size,is_demo=True,read_only=True,policy=POLICY,execution_authorized=False,connection='NOT CONNECTED')
