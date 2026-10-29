"""Stage 26 derived indexes over existing evidence. No new evidence store or execution path."""
from app.integrations.cebeci_preparation import authorize
from app.integrations.cebeci_account_preparation import FIELDS, GROUPS, RULE_VERSION, evidence_requirements
from app.integrations.cebeci_prerequisites import KEYS
from app.integrations.cebeci_manual import FINDINGS

# Join keys only: labels, owners, evidence, observations and decisions stay in their source models.
MATRIX_FIELDS={
 'IDENTITY':('ROUTER_IDENTITY','ROS6_LAB'),
 'ADDRESS':('SOURCE_ACCOUNT','SOURCE_SERVICE','SOURCE_FIREWALL','IPSEC_PATH'),
 'ISOLATION':('IPSEC_AUTH','IPSEC_PATH','V1_IMPACT'),
 'CERTIFICATE':('TLS_CLIENT','TLS_CHAIN','TLS_NAME','TLS_VALIDITY','TLS_PIN'),
 'PRIVILEGE':('ACCOUNT_SEPARATE','ACCOUNT_AUTH','POLICY_EXACT','ROS6_LAB'),
 'READ_SCOPE':('ROS6_LAB','POLICY_EXACT'),
 'SECRET_PROTECTION':('ACCOUNT_AUTH','AUDIT'),
 'AUDIT':('AUDIT',),
 'STOP':('STOP_OWNER','ROLLBACK','OPERATOR_REVIEW'),
}
STATES={'MISSING','CONFLICT','BLOCKED','UNKNOWN','STALE','UNVERIFIED','SYNTHETIC_REVIEW_PASS'}


def decision_packet(user,security):
    authorize(user)
    def node(parent,key):
        value=parent.get(key);return value if isinstance(value,dict) else {}
    def rows(parent,key):
        value=parent.get(key);return [row for row in value if isinstance(row,dict)] if isinstance(value,list) else []
    security=security if isinstance(security,dict) else {}
    prep=node(security,'account_preparation');manual=node(security,'manual_review');prereq=node(security,'prerequisites')
    fields=rows(prep,'evidence_fields');groups=rows(prep,'groups');matrix=rows(prereq,'matrix');findings=rows(manual,'findings')
    errors=[]
    def exact_ids(items,key,expected,code):
        ids=[item.get(key) for item in items]
        if len(ids)!=len(expected) or set(str(value) for value in ids)!=set(expected):errors.append(code)
    exact_ids(fields,'field',[key for key,*_ in FIELDS],'FIELD_REFERENCES_INVALID')
    exact_ids(groups,'id',[key for key,*_ in GROUPS],'GROUP_REFERENCES_INVALID')
    exact_ids(matrix,'criterion',KEYS,'MATRIX_REFERENCES_INVALID')
    exact_ids(findings,'id',['IDENTITY']+[key for key,*_ in FINDINGS],'MANUAL_REFERENCES_INVALID')
    if prep.get('evidence_rule_version')!=RULE_VERSION or any(
        any(row.get(name)!=value for name,value in evidence_requirements(row['field']).items()) or row.get('validity_seconds')!=300
        for row in fields if isinstance(row.get('field'),str) and row['field'] in {key for key,*_ in FIELDS}
    ):errors.append('EVIDENCE_ACCEPTANCE_RULES_INVALID')
    if any(row.get('status') not in STATES for row in fields):errors.append('UNSUPPORTED_EVIDENCE_STATE')
    if any(row.get('status')=='SYNTHETIC_REVIEW_PASS' and row.get('source')!='SYNTHETIC_FIXTURE' for row in fields):errors.append('UNTRUSTED_PASS_STATE')
    if prep.get('current_transport_contract')!='API_SSL' or node(security,'configuration').get('transport')!='API_SSL':errors.append('TLS_CONTRACT_INVALID')
    if any(prep.get(key) is not False for key in ('network_enabled','connection_allowed','account_creation_allowed','polling','automatic_retry','live_verification')):errors.append('CLOSED_BOUNDARY_INVALID')
    if prep.get('operator_approval')!='NOT_RECORDED' or prep.get('execution_authority')!='DENIED':errors.append('AUTHORITY_BOUNDARY_INVALID')
    options=rows(prep,'transport_options')
    if {row.get('id') for row in options}!={'A','B'} or len(options)!=2:errors.append('TRANSPORT_REFERENCES_INVALID')
    if any(row.get('approved') is not False or row.get('connection_allowed') is not False or
        (row.get('id')=='B' and row.get('status')!='BLOCKED_BY_CURRENT_TLS_CONTRACT') for row in options):errors.append('TRANSPORT_BOUNDARY_INVALID')
    fields=[row for row in fields if isinstance(row.get('field'),str) and row['field'] in {key for key,*_ in FIELDS}]
    findings=[row for row in findings if isinstance(row.get('id'),str) and row['id'] in {'IDENTITY',*(key for key,*_ in FINDINGS)}]
    buckets={key:[] for key in ('missing','manual','verified','expired','unverified','synthetic','unknown_time')}
    for row in fields:
        ref='field:'+str(row.get('field'));state=row.get('status')
        if state=='MISSING':buckets['missing'].append(ref)
        elif state=='STALE':buckets['expired'].append(ref)
        elif state=='SYNTHETIC_REVIEW_PASS' and row.get('source')=='SYNTHETIC_FIXTURE':buckets['synthetic'].append(ref)
        else:buckets['unverified'].append(ref)
        if row.get('source')=='MANUAL_OBSERVATION':buckets['manual'].append(ref)
        if row.get('observed_at') is None:buckets['unknown_time'].append(ref)
    for row in findings:
        ref='manual:'+str(row.get('id'));buckets['manual'].append(ref);buckets['unverified'].append(ref)
        if row.get('freshness')=='STALE':buckets['expired'].append(ref)
        if row.get('observed_at') is None:buckets['unknown_time'].append(ref)
    links=[dict(criterion=key,field_refs=list(MATRIX_FIELDS[key]),
        group_refs=[group for group,_,members in GROUPS if set(members)&set(MATRIX_FIELDS[key])],
        manual_refs=[row.get('id') for row in findings if key in row.get('criteria',[])]) for key in KEYS]
    return dict(version='CEBECI_DECISION_PACKET_V1',decision='NO_GO',connection='NOT CONNECTED',approval='APPROVAL REQUIRED',
        technical_suitability='NOT_VERIFIED',operator_approval='NOT_RECORDED',execution_authority='DENIED',
        connection_allowed=False,account_creation_allowed=False,network_enabled=False,polling=False,automatic_retry=False,
        sources_complete=not errors,integrity_errors=sorted(set(errors)),
        source_packet_ref='account_preparation.packet_sha256',matrix_links=links,
        evidence_buckets=buckets,counts={key:len(value) for key,value in buckets.items()},
        blocking_field_refs=[row.get('field') for row in fields if row.get('status')!='SYNTHETIC_REVIEW_PASS' or row.get('source')!='SYNTHETIC_FIXTURE'],
        hard_blocks=['LIVE_SECURITY_NOT_VERIFIED','SEPARATE_USER_APPROVAL_REQUIRED','EXECUTION_AUTHORITY_DENIED','API8728_TLS_EXCEPTION_NOT_GRANTED'],
        operator_questions=[
            'Tek CEBECI_TOWERS hedefi, güncel görünen kaynak /32, kanıt sahipleri ve UTC zamanları kim tarafından bağımsız incelenecek?',
            'A için sertifika/servis change planı mı, B için ayrı güvenlik politikası ve risk incelemesi mi hazırlanacak? Hiçbiri burada seçilmez/onaylanmaz.',
            'Ayrı read,api hesabının ROS6 lab kapsamı, V1 etkisizliği, süre/okuma bütçesi ve STOP/iptal sorumlusu belirlendi mi?',
            'Yedek kurtarılabilirlik ve sadece yeni V2 erişimine ait geri dönüş planı incelendi mi; ayrı açık kullanıcı onayı ve execution incelemesi için kapsam hazır mı?'],
        safe_next_steps=[
            'Önce mevcut onaylı offline envanter/lab/topoloji raporlarının gizli olmayan özetini, sorumlu rolünü ve gerçek gözlem zamanını tamamlayın; bilinmeyeni UNKNOWN bırakın.',
            'Eksik teknik kanıt, TLS/IPsec/source/V1 ve geri dönüş incelemesini ayrı sorumlularla planlayın. Credential, ham sertifika, private key, PSK veya SA paylaşmayın.',
            'Yeni gerçek erişim/change için ayrıca açık kullanıcı/operatör onayı ve dar yürütme yetkisi gerekir. Bu ekran onay almaz, hesap oluşturmaz, bağlantı veya deploy başlatmaz.'])
