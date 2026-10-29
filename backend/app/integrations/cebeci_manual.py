"""Curated operator report, not live evidence intake. No transport, secrets or persistence."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import Field, field_validator
from app.integrations.cebeci_access import AccessPlan, ClosedContract
from app.integrations.cebeci_prerequisites import EvidenceReceipt, review
from app.integrations.cebeci_preparation import authorize


class ManualIdentityRecord(ClosedContract):
    candidate_id: Literal['CEBECI_TOWERS']='CEBECI_TOWERS'
    source: Literal['OPERATOR_REPORTED_MANUAL']='OPERATOR_REPORTED_MANUAL'
    verification_type: Literal['MANUAL_OBSERVATION']='MANUAL_OBSERVATION'
    observed_at: datetime | None=None
    identity: str=Field(default='CEBECI_TOWERS',pattern=r'^[A-Za-z0-9_-]{1,64}$')
    model: str=Field(default='RB3011UiAS',pattern=r'^[A-Za-z0-9_-]{1,64}$')
    version: str=Field(default='6.49.19',pattern=r'^\d{1,2}\.\d{1,2}\.\d{1,3}$')

    @field_validator('observed_at',mode='before')
    @classmethod
    def aware_time(cls,value):
        return None if value is None else EvidenceReceipt.aware_time(value)


# Redacted findings supplied by the user. Account labels describe roles, never auth inputs.
# No raw command output, key, SA, password, login identifier or credential reference.
FINDINGS=(
 ('RESOURCES','Kaynak anlık görüntüsü','CPU %19; boş RAM 956 MiB; boş depolama 81.6 MiB. Kapasite/SLA veya güncel sağlık kanıtı değil.',('IDENTITY',)),
 ('API','Mevcut V1 API erişimi','API 8728 etkin; servis kaynağı 10.250.0.1/32 olarak bildirilmiş. V1/IPsec kullanımına ait; V2 yetkisi veya güncel kaynak eşleşmesi değil.',('ADDRESS','ISOLATION')),
 ('TLS','API-SSL / sertifika','API-SSL 8729 kapalı; certificate=none; sertifika listesi boş olarak bildirilmiş. TLS NOT VERIFIED.',('CERTIFICATE',)),
 ('V1_ACCOUNT','Mevcut webpanel rolü','V1 panel hesabı: webpanel-api grubunda read,write,test,api; kaynak sınırı 10.250.0.1/32. V2 salt okunur pilot için uygun değil; değiştirilmez.',('PRIVILEGE','SECRET_PROTECTION')),
 ('BROAD_ACCOUNTS','Geniş erişim riski','admin rolü full, kullanıcı kaynak sınırı boş; reception rolü write, geniş kaynak sınırı olarak bildirilmiş. Ayrı güvenlik iyileştirme planı; V1 hesaplarına müdahale yok.',('PRIVILEGE','ISOLATION')),
 ('IPSEC_POLICY','IPsec politika özeti','10.250.0.19/32 → 10.250.0.1/32 politikası active, ph2-count=1 olarak bildirilmiş. Ham/live SA bilgisi yok; V2 uçtan uca yol doğrulanmadı.',('ADDRESS','ISOLATION')),
 ('INPUT_FIREWALL','Görülen input kuralları','RADIUS UDP accept, dinamik hotspot, modem1 DNS drop, blocked-winbox listesi drop görülmüş. Kural sırası/tam kapsam/yönetim kaynağı güvenliği bilinmiyor; genel firewall güvencesi çıkarılamaz.',('ADDRESS','ISOLATION')),
)
# Manual statement versus enforceable evidence are deliberately separate.
ASSESSMENTS={
 'IDENTITY':('MATCH_REPORTED',('IDENTITY',),'Kimlik/model/build manuel bildirimde eşleşti; bağımsız doğrulama ve güncellik eksik.'),
 'ADDRESS':('PARTIAL_REPORTED',('API','IPSEC_POLICY','INPUT_FIREWALL'),'Geçmiş/tek zamanlı hedef ve V1 /32, V2 kaynak/yol onayı değildir.'),
 'ISOLATION':('NOT_VERIFIED',('API','IPSEC_POLICY','INPUT_FIREWALL','BROAD_ACCOUNTS'),'Aktif politika tam uçtan uca korumayı veya V1 izolasyonunu kanıtlamaz.'),
 'CERTIFICATE':('BLOCKED_REPORTED',('TLS',),'API-SSL kapalı/sertifikasız bildirilmiş; güncel TLS/zincir/SAN kanıtı yok.'),
 'PRIVILEGE':('UNSUITABLE_REPORTED',('V1_ACCOUNT','BROAD_ACCOUNTS'),'Mevcut write/test/full hesapları pilot hesabı olamaz; ayrı minimum yetki ve ROS6 lab gerekli.'),
 'READ_SCOPE':('MISSING',(),'Beş metadata print kaynağının tam build lab kanıtı ve ayrı kapsam incelemesi eksik.'),
 'SECRET_PROTECTION':('NOT_VERIFIED',('V1_ACCOUNT',),'Bu rapor sır içermez; ayrı pilot credential yaşam döngüsü/redaction kanıtı henüz yok.'),
 'AUDIT':('MISSING',(),'Gözlem zamanı, kaynak güncelliği ve uygulama öncesi audit baseline kanıtı eksik.'),
 'STOP':('MISSING',(),'Atanmış STOP/iptal sorumlusu, güvenli geri dönüş kanıtı ve ayrı açık onay eksik.'),
}
OPTIONS=(
 dict(id='A',label='Doğrulanmış TLS ile API-SSL',status='BLOCKED_REPORTED',current_contract='TLS_REQUIRED_DESIGN_ONLY',
      encryption='Doğrulanmış TLS 1.2+; zincir/SAN-IP/zaman/uyum kanıtı zorunlu. Şu an servis kapalı ve sertifika yok bildirilmiş.',
      authentication='Sunucu kimliği zincir ve isimle doğrulanmalı; ayrı pilot hesabı gerekir. Port veya IPsec tek başına yeterli değil.',
      source_isolation='Ayrıca incelenmiş tek hedef ve NAT sonrası /32; hesap, servis, input sınırları birlikte kanıtlanmalı.',
      ros6_limits='6.49.19 TLS/cipher/client ve read,api dosya/alan etkileri lab gerektirir; anonymous DH veya verification bypass yok.',
      v1_impact='Sertifika/servis ekleme canlı değişikliktir; V1 bağımlılık ve geri dönüşü ayrı incelenmeden uygulanmaz.',
      operational_risk='PKI yönetimi ve süre/iptal yükü; V1 etkisi bilinmiyor. Mevcut sözleşmeye yön olarak uyumlu, uygulama yok.'),
 dict(id='B',label='Doğrulanmış IPsec yolu üzerinden API 8728',status='BLOCKED_BY_CURRENT_CONTRACT',current_contract='SEPARATE_SECURITY_REVIEW_REQUIRED',
      encryption='API katmanında TLS yok; yalnız kanıtlanmış IPsec segmenti ağ koruması sağlayabilir. Tünel dışı uç/yol riski sürer.',
      authentication='TLS sunucu kimliği yok; ayrı hesap ve bağımsız tek-router kimlik/yol kanıtı gerekir. API login gizliliği tünel kapsamına bağlı.',
      source_isolation='V1 servis /32 kaynağını paylaşmak V2 izolasyonu değildir. NAT/selectors/yönler ve açık yola kaçmama kanıtlanmalı.',
      ros6_limits='ROS6 login parolayı protokolde açık iletir; read,api dar ACL değildir. active/ph2-count yeterli uyumluluk/güvenlik kanıtı değil.',
      v1_impact='Mevcut V1 servis/tünel/hesaplarına bağımlılık ve ortak kaynak riski; mevcut ayarlar değiştirilmez.',
      operational_risk='Tünel kaybı/yol değişiminde açık API ile devam edilemez. Aşama 22 TLS zorunluluğuna aykırı; ayrı sözleşme incelemesi/onay olmadan kullanılamaz.'),
)


def manual_review(user, *, snapshot:ManualIdentityRecord|None=None, now:datetime|None=None):
    authorize(user)
    try:snapshot=ManualIdentityRecord.model_validate(dict((snapshot or ManualIdentityRecord()).__dict__))
    except (ValueError,AttributeError):raise ValueError('MANUAL_REPORT_CONTRACT_REJECTED') from None
    now=now or datetime.now(timezone.utc)
    if now.utcoffset() is None:raise ValueError('AWARE_ASSESSMENT_CLOCK_REQUIRED')
    freshness=('UNKNOWN' if snapshot.observed_at is None or snapshot.observed_at>now else
        'STALE' if now-snapshot.observed_at>=timedelta(minutes=5) else 'WITHIN_REVIEW_WINDOW_NOT_VERIFIED')
    expected=AccessPlan()
    identity_match=(snapshot.identity,snapshot.model,snapshot.version)==(expected.expected_identity,expected.expected_model,expected.expected_version)
    baseline=review(user,now=now)
    matrix=[]
    for original in baseline['matrix']:
        state,refs,reason=ASSESSMENTS[original['criterion']]
        if original['criterion']=='IDENTITY' and not identity_match:state,reason='CONFLICT','Manuel identity/model/build adayla çelişiyor; STOP.'
        matrix.append({**original,'manual_status':state,'manual_reason':reason,'observation_ids':list(refs),
            'manual_freshness':freshness,'manually_reported':bool(refs),'independently_verified':False})
    findings=[dict(id='IDENTITY',label='Identity / model / RouterOS',summary=f'{snapshot.identity} · {snapshot.model} · {snapshot.version}',criteria=['IDENTITY'])]
    findings.extend(dict(id=key,label=label,summary=summary,criteria=list(criteria)) for key,label,summary,criteria in FINDINGS)
    for finding in findings:finding.update(source=snapshot.source,verification_type=snapshot.verification_type,observed_at=snapshot.observed_at.isoformat() if snapshot.observed_at else None,freshness=freshness,independently_verified=False)
    return dict(version='CEBECI_MANUAL_REVIEW_V1',source=snapshot.source,verification_type=snapshot.verification_type,
        observed_at=snapshot.observed_at.isoformat() if snapshot.observed_at else None,freshness=freshness,
        identity_match_reported=identity_match,live_identity_verified=False,decision='NO_GO',connection='NOT CONNECTED',approval='APPROVAL REQUIRED',
        technical_suitability='NOT_VERIFIED',operator_approval='NOT_RECORDED',execution_authority='DENIED',connection_allowed=False,
        network_enabled=False,automatic_retry=False,polling=False,credential_storage='NONE',
        findings=findings,matrix=matrix,access_options=[{**option,'approved':False,'connection_allowed':False} for option in OPTIONS],
        critical_risks=['TLS_DISABLED_CERTIFICATE_ABSENT_REPORTED','EXISTING_ACCOUNT_WRITE_TEST_NOT_READ_ONLY',
            'BROAD_ADMIN_RECEPTION_ACCESS_REPORTED','V2_PATH_SOURCE_FIREWALL_NOT_VERIFIED','OBSERVATION_TIME_UNKNOWN_OR_UNVERIFIED',
            'AUDIT_STOP_ROLLBACK_APPROVAL_MISSING']+([] if identity_match else ['MANUAL_IDENTITY_MODEL_VERSION_CONFLICT']),
        remaining_evidence=[row['criterion'] for row in matrix],stop_conditions=['WRONG_IDENTITY','UNEXPECTED_WRITE','TLS_OR_IPSEC_UNVERIFIED','V1_IMPACT','SOURCE_MISMATCH','AUDIT_OR_ROLLBACK_MISSING'],
        account_plan=dict(policies=['read','api'],status='LAB_VERIFICATION_REQUIRED',separate_v2_account=True,existing_accounts_unchanged=True),
        plan_only=True,execution_endpoints_added=False)
