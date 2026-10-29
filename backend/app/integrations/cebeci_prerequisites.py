"""Stage 23 offline review metadata; no collection, approval storage or transport."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import Field, field_validator
from app.integrations.cebeci_access import ClosedContract, assess
from app.integrations.cebeci_preparation import authorize

# TTLs are review policy maxima, not proof of device state. Any relevant change invalidates early.
MATRIX = (
 ('IDENTITY', 'Router identity / model / RouterOS', ('IDENTITY','MODEL','VERSION'), 300, 'NETWORK_OWNER', 'Ayrı incelenmiş envanter ve tam build lab raporu', 'Kimlik/model/build değerlerini bağımsız envanter kaydıyla karşılaştır', 'Kimlik/model/build çelişkisi'),
 ('ADDRESS', 'Yönetim adresi / merkezi kaynak', ('MANAGEMENT_ADDRESS','SOURCE_ALLOWLIST','NETWORK_PATH'), 300, 'NETWORK_OWNER', 'Güncel hedef ve NAT sonrası tek kaynak /32 inceleme özeti', 'İki sorumlu güncel adres/yol kayıtlarını eşleştirir; geçmiş adres kanıt değildir', 'Hedef/kaynak/yol belirsiz veya farklı'),
 ('ISOLATION', 'IPsec yönetim yolu / V1 izolasyonu', ('V1_ISOLATION','NETWORK_PATH'), 300, 'ISOLATION_OWNER', 'Maskeli yol topolojisi ve V1 etki incelemesi', 'Mevcut onaylı topoloji/baseline kayıtları üzerinde V2 ayrımını incele; SA alma', 'V1 etkisi, ortak credential veya belirsiz izolasyon'),
 ('CERTIFICATE', 'API-SSL zincir / SAN-IP', ('TLS','CERTIFICATE_CHAIN','CERTIFICATE_NAME','CERTIFICATE_PIN','CERTIFICATE_VALIDITY'), 300, 'SECURITY_REVIEWER', 'Public fingerprint ve CA/SAN/validity inceleme sonucu; ham sertifika yok', 'Tam ROS6 build lab raporu ve public metadata üzerinden zincir/SAN/zamanı bağımsız kontrol et', 'TLS/isim/zincir/pin uyuşmazlığı veya doğrulanamayan uyumluluk'),
 ('PRIVILEGE', 'Ayrı minimum yetkili ROS6 hesabı', ('ROUTER_PERMISSION','AUTHENTICATION','MINIMUM_PRIVILEGE','ROS6_FIELD_LAB'), 86400, 'SECURITY_REVIEWER', 'Ayrı hesap/policy ve tam build lab negatif test özeti; hesap adı yok', 'read,api adayını dosya/yan etki ve forbidden kaynak lab testleriyle incele', 'Ek policy, hesap paylaşımı veya lab kanıtı eksik'),
 ('READ_SCOPE', 'İzinli salt okunur kaynaklar', ('ROS6_FIELD_LAB',), 86400, 'SECURITY_REVIEWER', 'Stage 22 beş menü/alan sözleşmesinin revision hash ve lab kapsamı', 'Exact print allowlist ve ek alan/yazma reddi test raporunu karşılaştır', 'Allowlist dışı kaynak/alan/yazma gereksinimi'),
 ('SECRET_PROTECTION', 'Kimlik bilgisi / gizli veri koruması', ('AUTHENTICATION','AUDIT'), 86400, 'SECURITY_REVIEWER', 'Redaction/retention ve ayrı credential yönetimi tasarım incelemesi', 'Sadece sabit sonuç kodu/hash/rol/zaman; raw yanıt veya sır kopyalama', 'Parola/PSK/private key/SA talebi veya sızıntı'),
 ('AUDIT', 'Audit / veri güncelliği', ('AUDIT','FRESHNESS'), 300, 'AUDIT_OWNER', 'UTC zamanlı redacted inceleme ve korunmuş baseline özeti', 'Kaynak saati, 5 dakika üst sınırı ve değişmez baseline/hash kontrolü', 'Eksik audit, gelecek zaman, stale veya çelişkili kayıt'),
 ('STOP', 'Acil durdurma / erişim iptali', ('STOP_OWNER',), 86400, 'INCIDENT_OWNER', 'Sorumlu rolü, süre bütçesi ve onay gerektiren iptal runbook incelemesi', 'Yeni V2 okuyucuyu durdurma; V1/audit korunması ve gelecekteki iptal sorumlusunu masa başında doğrula', 'Sorumlu/bütçe/iptal prosedürü eksik'),
)
KEYS=tuple(row[0] for row in MATRIX)

class EvidenceReceipt(ClosedContract):
    criterion: Literal['IDENTITY','ADDRESS','ISOLATION','CERTIFICATE','PRIVILEGE','READ_SCOPE','SECRET_PROTECTION','AUDIT','STOP']
    outcome: Literal['PASS','FAILED','UNKNOWN','CONFLICT']='UNKNOWN'
    source: Literal['SYNTHETIC_FIXTURE','OFFLINE_UNVERIFIED']='OFFLINE_UNVERIFIED'
    reviewer_role: Literal['NETWORK_OWNER','ISOLATION_OWNER','SECURITY_REVIEWER','AUDIT_OWNER','INCIDENT_OWNER']
    artifact_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    policy_packet_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    reviewed_at: datetime
    expires_at: datetime

    @field_validator('reviewed_at','expires_at',mode='before')
    @classmethod
    def aware_time(cls,value):
        if not isinstance(value,(str,datetime)):raise ValueError('UTC_AWARE_TIME_REQUIRED')
        parsed=datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
        if parsed.utcoffset() is None:raise ValueError('UTC_AWARE_TIME_REQUIRED')
        return parsed


def review(user, receipts:tuple[EvidenceReceipt,...]=(), *, plan=None,evidence=None,now=None):
    authorize(user)
    now=now or datetime.now(timezone.utc)
    security=assess(user,plan,evidence,now=now)  # Existing security decisions remain authoritative.
    try: receipts=tuple(EvidenceReceipt.model_validate(dict(row.__dict__)) for row in receipts)
    except (ValueError,AttributeError):raise ValueError('EVIDENCE_CONTRACT_REJECTED') from None
    gates={row['criterion']:row['status'] for row in security['checklist']}
    rows=[]
    for key,label,bindings,ttl,owner,proof,method,stop in MATRIX:
        matches=[row for row in receipts if row.criterion==key]
        state='MISSING';reason='EVIDENCE_MISSING';receipt=matches[0] if len(matches)==1 else None
        if len(matches)>1:state,reason='CONFLICT','DUPLICATE_EVIDENCE'
        elif receipt:
            state,reason='REVIEW_READY','OFFLINE_REVIEW_ONLY'
            if receipt.outcome!='PASS':state,reason=receipt.outcome,'REVIEW_'+receipt.outcome
            elif receipt.reviewer_role!=owner:state,reason='INVALID','REVIEWER_ROLE_MISMATCH'
            elif receipt.policy_packet_sha256!=security['packet_digest']:state,reason='CONFLICT','POLICY_PACKET_CHANGED'
            elif receipt.reviewed_at>now or receipt.expires_at<=receipt.reviewed_at or receipt.expires_at>receipt.reviewed_at+timedelta(seconds=ttl):state,reason='INVALID','INVALID_VALIDITY_WINDOW'
            elif receipt.expires_at<=now or now-receipt.reviewed_at>timedelta(seconds=ttl):state,reason='STALE','EVIDENCE_EXPIRED'
            elif any(gates[binding]!='PASS' for binding in bindings):state,reason='BLOCKED','SECURITY_GATE_NOT_PASS'
        rows.append(dict(criterion=key,label=label,status=state,reason_code=reason,security_criteria=list(bindings),
            evidence_type=proof,verification_method=method,validity_seconds=ttl,invalidate_on_change=True,responsible_role=owner,stop_condition=stop,
            reviewed_at=receipt.reviewed_at.isoformat() if receipt else None,expires_at=receipt.expires_at.isoformat() if receipt else None,
            source=receipt.source if receipt else 'NOT_PROVIDED',artifact_sha256=receipt.artifact_sha256 if receipt else None))
    return dict(version='CEBECI_PREREQUISITES_V1',decision='NO_GO',connection='NOT CONNECTED',
        technical_suitability='OFFLINE_REVIEW_READY' if all(row['status']=='REVIEW_READY' for row in rows) else 'NOT_VERIFIED',
        operator_approval='NOT_RECORDED',execution_authority='DENIED',connection_allowed=False,
        automatic_go=False,policy_packet_sha256=security['packet_digest'],matrix=rows,
        missing_prerequisites=[row['criterion'] for row in rows if row['status']!='REVIEW_READY'],
        reasons=['REAL_PILOT_SEPARATE_EXPLICIT_APPROVAL_REQUIRED','LIVE_SECURITY_NOT_VERIFIED','EXECUTION_DISABLED'],
        evidence_intake='OFFLINE_TYPED_TEST_ONLY_NO_UPLOAD',approval='APPROVAL REQUIRED')
