"""Stage 25 synthetic preparation only. No account provisioner, credential or transport."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Literal
from pydantic import Field, field_validator
from app.integrations.cebeci_access import AccessPlan, ClosedContract, READ_SCOPE, assess
from app.integrations.cebeci_prerequisites import EvidenceReceipt
from app.integrations.cebeci_preparation import authorize

VERSION='CEBECI_ACCOUNT_PREPARATION_V1'
FORBIDDEN_POLICIES=('write','policy','sensitive','password','reboot','test','ftp','ssh','winbox','telnet','local','web','sniff','romon','rest-api')
# Separate evidence IDs: no TLS, tunnel, source or V1 inference from another proof.
FIELDS=(
 ('ACCOUNT_SEPARATE','Ayrı V2 hesabı','V1/webpanel/admin/reception paylaşılmayan ayrı hesap tasarım incelemesi.'),
 ('ACCOUNT_AUTH','Pilot kimlik doğrulaması','Ayrı auth yaşam döngüsü ve sır almadan doğrulama/iptal planı.'),
 ('POLICY_EXACT','Exact minimum policy','Yalnız read,api özel grup; geniş veya ek policy yok.'),
 ('ROS6_LAB','ROS6 minimum yetki lab','Tam 6.49.19 üzerinde menü/alan/dosya/yan etki negatif lab raporu; read,api yeterli varsayılmaz.'),
 ('TLS_CLIENT','TLS istemci uyumu','6.49.19 TLS 1.2+ istemci/cipher lab kanıtı; anonymous DH/fallback yok.'),
 ('IPSEC_AUTH','IPsec kimlik doğrulaması','Peer kimliği ve yetkili auth inceleme sonucu; PSK/private key/SA alınmaz.'),
 ('IPSEC_PATH','IPsec yönetim yolu','Tek-router iki yön/selector/NAT/tünel dışına kaçmama incelemesi; active tek başına yeterli değil.'),
 ('SOURCE_ACCOUNT','Hesap kaynak sınırı','Cihazın gördüğü güncel V2 /32; mevcut V1 /32 otomatik atanmaz.'),
 ('SOURCE_SERVICE','Servis kaynak sınırı','Seçilen servis için ayrı kaynak izolasyonu incelemesi; mevcut servise müdahale yok.'),
 ('SOURCE_FIREWALL','Input kaynak sınırı','Tam input kapsam/sıra/yol incelemesi; kısmi kurallar genel güvenlik garantisi değil.'),
 ('ROUTER_IDENTITY','Tek router kimliği','Güncel identity/model/tam build ve tek yönetim hedefi eşleşmesi.'),
 ('TLS_CHAIN','TLS güven zinciri','Güvenilen CA zinciri inceleme sonucu; ham sertifika/private key alınmaz.'),
 ('TLS_NAME','TLS SAN/IP eşleşmesi','İncelenmiş tek hedefin sertifika ismi/IP eşleşmesi; bypass yok.'),
 ('TLS_VALIDITY','TLS sertifika geçerliliği','Zaman/kullanım/iptal incelemesi; kapalı/sertifikasız servis kanıt sayılmaz.'),
 ('TLS_PIN','Public sertifika pini','Ayrı incelenmiş public SHA-256 pin; zincir/SAN yerine geçmez.'),
 ('V1_IMPACT','V1 izolasyonu','Mevcut hesap/grup/API/IPsec/abonelerin değişmeyeceği ve baseline etkisizlik incelemesi.'),
 ('AUDIT','Audit hazırlığı','Sır içermeyen baseline, sonuç kodu/rol/hash/UTC zamanı ve kayıt koruma planı.'),
 ('STOP_OWNER','STOP hazırlığı','Atanmış sorumlu, timebox/okuma bütçesi ve ilk hatada durdurma prosedürü.'),
 ('ROLLBACK','Geri dönüş hazırlığı','Güvenli yedek kurtarılabilirlik incelemesi ve yalnız yeni V2 erişimini iptal planı; dosya alınmaz.'),
 ('OPERATOR_REVIEW','Operatör plan incelemesi','Aday/kapsam/süre/change/iptal sorumluluğu incelemesi; gerçek açık onay ayrı ve bu fazda kaydedilmez.'),
)
GROUPS=(
 ('PILOT_ACCOUNT','Ayrı V2 pilot hesabı',('ACCOUNT_SEPARATE','ACCOUNT_AUTH')),
 ('MINIMUM_PRIVILEGE','Minimum yetki doğrulaması',('POLICY_EXACT','ROS6_LAB')),
 ('SECURE_TRANSPORT','Güvenli taşıma yöntemi',('TLS_CLIENT','IPSEC_AUTH','IPSEC_PATH')),
 ('SOURCE_IP','Kaynak IP kısıtlaması',('SOURCE_ACCOUNT','SOURCE_SERVICE','SOURCE_FIREWALL')),
 ('IDENTITY_CERTIFICATE','Kimlik ve sertifika doğrulaması',('ROUTER_IDENTITY','TLS_CHAIN','TLS_NAME','TLS_VALIDITY','TLS_PIN')),
 ('V1_ISOLATION','V1 izolasyonu',('V1_IMPACT',)),
 ('STOP_ROLLBACK','STOP ve rollback hazırlığı',('AUDIT','STOP_OWNER','ROLLBACK')),
 ('OPERATOR_APPROVAL','Operatör onayı',('OPERATOR_REVIEW',)),
)


# Stage 27 enriches the same twenty fields; no second evidence or decision model.
RULE_VERSION='CEBECI_EVIDENCE_ACCEPTANCE_V1'
OFFLINE='OFFLINE_REPORT_REVIEW'
LIVE='EXPLICIT_APPROVAL_BEFORE_LIVE_VERIFICATION_OR_CHANGE'
# acceptance, expected source, safe completion, approval scope, STOP condition
EVIDENCE_RULES={
 'ACCOUNT_SEPARATE':('V1 hesapları paylaşılmadan ayrı aday/kapsam/iptal sahibi; mevcut hesap değişmez.', 'Yetkili hesap sahibi tarafından maskeli ayrı hesap tasarım/inceleme özeti', 'Mevcut onaylı hesap envanterini offline incele; yeni hesap veya cihaz sorgusu ayrı onay bekler.', LIVE, 'Ortak V1 hesabı, yetkisiz oluşturma veya sorumlu eksikliği'),
 'ACCOUNT_AUTH':('Ayrı auth yaşam döngüsü, saklamama ve iptal süreci incelenmiş; credential alınmamış.', 'Güvenlik sorumlusunun sır içermeyen auth süreç raporu', 'Kurumdaki auth/iptal prosedürünü incele; hesap adı/parola/token isteme.', OFFLINE, 'Credential/PSK/private key talebi veya V1 auth paylaşımı'),
 'POLICY_EXACT':('Yalnız özel read,api aday seti; ek/eksik/tekrarlı policy yok; yeterlilik ayrıca lab kanıtı.', 'Sır içermeyen policy kapsam incelemesi ve kanonik hesap sözleşmesi', 'Aday policy listesini offline karşılaştır; eksik alan için yetki artırma.', OFFLINE, 'write/policy/sensitive/password/reboot/test veya başka ek yetki'),
 'ROS6_LAB':('Tam 6.49.19 üzerinde beş metadata print alanı ve dosya/yan etki sınırları negatif lab raporuyla incelenmiş.', 'İzole lab sorumlusunun tam build ve kapsamı belirtilmiş raporu', 'Var olan onaylı lab raporunu incele; üretimde negatif yazma testi yapma.', OFFLINE, 'Build/kapsam uyuşmazlığı, read,api yeterliliğini varsayma'),
 'TLS_CLIENT':('TLS 1.2+ istemci/cipher uyumu; anonymous DH, eski protokol ve bypass/fallback yok.', 'Tam 6.49.19 izole TLS uyumluluk lab raporu', 'Mevcut lab raporunu incele; gerçek handshake veya servis açma için ayrı onay gerekir.', OFFLINE, 'Legacy/anonymous DH veya doğrulama kapatma gereksinimi'),
 'IPSEC_AUTH':('Peer kimliği ve auth yönteminin bağımsız incelemesi; active/ph2-count yeterli değil.', 'Yetkili ağ/güvenlik sahibinin maskeli peer kimlik doğrulama incelemesi', 'Onaylı mevcut peer inceleme özetini kullan; PSK/anahtar/SA isteme; canlı sorgu ayrı onay bekler.', LIVE, 'Peer kimliği/auth belirsizliği veya gizli SA/PSK talebi'),
 'IPSEC_PATH':('Tek-router iki yön/selector/NAT ve tünel dışına kaçmama kanıtı; V1 etkisi ayrı incelenir.', 'Ağ sahibinin maskeli güncel yol/topoloji inceleme raporu', 'Mevcut onaylı diyagramı offline incele; ping/API/tünel testi bu aşamada yok.', LIVE, 'Açık yola kaçış, yanlış hedef veya doğrulanamayan IPsec sınırı'),
 'SOURCE_ACCOUNT':('Cihazın gördüğü güncel V2 tek /32 ile hesap sınırı eşleşmiş; eski V1 /32 devralınmamış.', 'Hesap ve ağ sahibinin maskeli hedef/kaynak eşleştirme incelemesi', 'Mevcut yetkili raporları karşılaştır; kullanıcı/source değişimi veya güncel sorgu ayrı onay bekler.', LIVE, 'Geniş/yanlış/UNKNOWN kaynak veya V1 kaynağını otomatik atama'),
 'SOURCE_SERVICE':('Seçilen servis ve güncel V2 /32 sınırı incelenmiş; mevcut V1 servisi etkilenmez.', 'Yetkili servis/ağ sahibinin kaynak kapsam inceleme özeti', 'Mevcut servis inceleme raporunu kullan; API açma/taşıma veya address değiştirme yok.', LIVE, 'Servis/source belirsizliği veya V1 servis etkisi'),
 'SOURCE_FIREWALL':('Tam input sırası/kapsam/yol/source incelemesi; kısmi kurallar genel güvenlik kanıtı değil.', 'Yetkili firewall sahibinin sır içermeyen tam kapsam değerlendirmesi', 'Var olan onaylı kural değerlendirme özetini incele; raw export veya firewall değişimi yapma.', LIVE, 'Eksik sıra/default politika/yönetim kapsamı veya geniş kaynak riski'),
 'ROUTER_IDENTITY':('CEBECI_TOWERS/RB3011UiAS/6.49.19 ve tek güncel yönetim hedefi bağımsız eşleşmiş.', 'Ağ sahibinin bağımsız envanter ve taze zamanlı kimlik incelemesi', 'Mevcut envanter raporunu karşılaştır; geçmiş 10.250.0.19 endpoint sayılmaz, yeni sorgu ayrı onay bekler.', LIVE, 'Yanlış identity/model/build/hedef veya UNKNOWN gözlem zamanı'),
 'TLS_CHAIN':('İncelenmiş trust store ve eksiksiz CA zinciri; public pin tek başına yeterli değil.', 'Güvenlik sahibinin public metadata üzerinden zincir inceleme sonucu', 'Mevcut maskeli zincir değerlendirmesini incele; ham sertifika/private key alma.', LIVE, 'Güvenilmeyen/eksik zincir veya verification bypass'),
 'TLS_NAME':('Tek incelenmiş hedef SAN/IP ile exact eşleşmiş; hostname kontrolü atlanmamış.', 'Güvenlik sahibinin hedef-SAN/IP eşleşme inceleme özeti', 'Mevcut public isim eşleşme raporunu karşılaştır; gerçek TLS testi ayrı onay bekler.', LIVE, 'SAN/IP uyuşmazlığı veya hostname doğrulamasını kapatma'),
 'TLS_VALIDITY':('Sertifika zaman/kullanım/iptal incelemesi geçerli; kapalı/sertifikasız servis yeterli değil.', 'Güvenlik sahibinin public validity/usage/revocation inceleme sonucu', 'Mevcut geçerlilik raporunu incele; yeni sertifika yükleme veya servis açma yok.', LIVE, 'Süre dolması/iptal/kullanım belirsizliği veya certificate=none'),
 'TLS_PIN':('Ayrı gözden geçirilmiş public SHA-256 pin eşleşir; zincir ve isim kanıtları da gerekir.', 'Güvenlik sahibinin public fingerprint karşılaştırma sonucu', 'Yalnız public pin inceleme sonucunu kullan; secret/private key veya sır hash alma.', LIVE, 'Pin uyuşmazlığı, eksik pin veya zincir yerine pin kullanma'),
 'V1_IMPACT':('Mevcut V1 hesap/API/IPsec/abonelerin korunması ve etkisizlik baseline incelemesi.', 'V1 izolasyon sorumlusunun mevcut onaylı baseline/etki raporu', 'Mevcut offline etki raporunu incele; V1 sisteme bağlanma veya konfigürasyon değiştirme.', LIVE, 'V1 etkisi/paylaşılan hesap/yol riski veya baseline eksikliği'),
 'AUDIT':('Sır içermeyen baseline ve UTC/ofset zamanlı sonuç/rol/paket referansı korunur.', 'Audit sahibinin redaction/retention ve baseline inceleme özeti', 'Mevcut audit süreç raporunu offline incele; raw yanıt veya abone/audit silme yok.', OFFLINE, 'Audit/baseline eksikliği veya credential/raw SA kaydı'),
 'STOP_OWNER':('Atanacak sorumlu rol/irtibat, süre-okuma bütçesi ve ilk hatada durdurma planı açık.', 'Operasyon sahibinin görev/timebox/STOP runbook incelemesi', 'Sorumluluk ve bütçe planını masa başında tamamla; gerçek süreç başlatma/durdurma yok.', OFFLINE, 'Sorumlu/bütçe belirsizliği veya otomatik retry planı'),
 'ROLLBACK':('Güvenli yedek kurtarılabilirlik incelemesi ve yalnız yeni V2 erişimine özel iptal planı.', 'Yetkili yedek/operasyon sahibinin gizli olmayan restore/iptal planı değerlendirmesi', 'Mevcut kurtarılabilirlik raporunu incele; backup dosyası alma, restore veya canlı iptal uygulama.', OFFLINE, 'Geri dönüş kanıtı eksikliği veya V1/global restore gereksinimi'),
 'OPERATOR_REVIEW':('Aday/kapsam/yöntem/timebox/change/iptal planı incelenmiş; gerçek onay/yetki ayrı.', 'Sorumlu operatörün yalnız plan incelemesi; gerçek onay dış süreçte ayrıca gerekir', 'İnceleme kapsamını belgele; bu ekranda onay verme veya yürütme izni kaydetme.', 'SEPARATE_EXPLICIT_USER_APPROVAL_AND_EXECUTION_REVIEW', 'Plan incelemesini gerçek onay/yürütme yetkisi sayma'),
}
RULE_KEYS=('acceptance_criteria','expected_source','completion_method','approval_requirement','stop_condition')

def evidence_requirements(key):
    return dict(zip(RULE_KEYS,EVIDENCE_RULES[key],strict=True))

class PilotAccountContract(ClosedContract):
    candidate_id:Literal['CEBECI_TOWERS']='CEBECI_TOWERS'
    policies:tuple[str,...]=('read','api')
    account_reuse:Literal['FORBIDDEN']='FORBIDDEN'
    provisioning_method:Literal['OPERATOR_SECURE_MANAGEMENT_SESSION']='OPERATOR_SECURE_MANAGEMENT_SESSION'
    initial_account_state:Literal['DISABLED']='DISABLED'
    existing_object_action:Literal['STOP_PRESERVE_EXISTING']='STOP_PRESERVE_EXISTING'
    credential_intake:Literal['NONE']='NONE'
    @field_validator('policies')
    @classmethod
    def minimum_candidate_only(cls,value):
        if len(value)!=2 or set(value)!={'read','api'}:raise ValueError('EXACT_READ_API_CANDIDATE_REQUIRED')
        return ('read','api')

class PreparationClaim(ClosedContract):
    candidate_id:Literal['CEBECI_TOWERS']='CEBECI_TOWERS'
    field:Literal['ACCOUNT_SEPARATE','ACCOUNT_AUTH','POLICY_EXACT','ROS6_LAB','TLS_CLIENT','IPSEC_AUTH','IPSEC_PATH','SOURCE_ACCOUNT','SOURCE_SERVICE','SOURCE_FIREWALL','ROUTER_IDENTITY','TLS_CHAIN','TLS_NAME','TLS_VALIDITY','TLS_PIN','V1_IMPACT','AUDIT','STOP_OWNER','ROLLBACK','OPERATOR_REVIEW']
    outcome:Literal['PASS','FAILED','UNKNOWN']='UNKNOWN'
    source:Literal['SYNTHETIC_FIXTURE','OFFLINE_UNVERIFIED','MANUAL_OBSERVATION']='OFFLINE_UNVERIFIED'
    observed_at:datetime|None=None
    packet_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    @field_validator('observed_at',mode='before')
    @classmethod
    def aware_time(cls,value):return None if value is None else EvidenceReceipt.aware_time(value)


def prepare(user,claims:tuple[PreparationClaim,...]=(),*,contract:PilotAccountContract|None=None,now:datetime|None=None):
    authorize(user)
    try:
        contract=PilotAccountContract.model_validate(dict((contract or PilotAccountContract()).__dict__))
        claims=tuple(PreparationClaim.model_validate(dict(claim.__dict__)) for claim in claims)
    except (ValueError,AttributeError):raise ValueError('ACCOUNT_PREPARATION_CONTRACT_REJECTED') from None
    now=now or datetime.now(timezone.utc)
    base=assess(user,now=now)  # Preserve the current closed policy, auth and aware-clock boundary.
    packet=sha256(json.dumps([VERSION,base['packet_digest'],contract.model_dump(mode='json'),dict(READ_SCOPE),FIELDS,GROUPS,RULE_VERSION,EVIDENCE_RULES],sort_keys=True).encode()).hexdigest()
    fields=[]
    for key,label,required in FIELDS:
        matches=[claim for claim in claims if claim.field==key]
        status,reason='MISSING','EVIDENCE_MISSING'
        claim=matches[0] if len(matches)==1 else None
        if len(matches)>1:status,reason='CONFLICT','DUPLICATE_EVIDENCE'
        elif claim:
            if claim.packet_sha256!=packet:status,reason='CONFLICT','POLICY_PACKET_CHANGED'
            elif claim.outcome=='FAILED':status,reason='BLOCKED','NEGATIVE_REVIEW'
            elif claim.outcome=='UNKNOWN':status,reason='UNKNOWN','REVIEW_UNKNOWN'
            elif claim.observed_at is None or claim.observed_at>now:status,reason='UNKNOWN','OBSERVATION_TIME_UNKNOWN'
            elif now-claim.observed_at>=timedelta(minutes=5):status,reason='STALE','EVIDENCE_EXPIRED'
            elif claim.source!='SYNTHETIC_FIXTURE':status,reason='UNVERIFIED','MANUAL_OR_OFFLINE_NOT_VERIFIED'
            else:status,reason='SYNTHETIC_REVIEW_PASS','SIMULATION_NOT_REAL_VERIFICATION'
        fields.append(dict(field=key,label=label,status=status,reason_code=reason,evidence_required=required,
            source=claim.source if claim else 'NOT_PROVIDED',observed_at=claim.observed_at.isoformat() if claim and claim.observed_at else None,validity_seconds=300,**evidence_requirements(key)))
    by_key={row['field']:row for row in fields}
    groups=[dict(id=key,label=label,fields=list(keys),status='NOT_RECORDED' if key=='OPERATOR_APPROVAL' else
        'SYNTHETIC_REVIEW_ONLY' if all(by_key[k]['status']=='SYNTHETIC_REVIEW_PASS' for k in keys) else 'NOT_READY',
        missing_fields=[k for k in keys if by_key[k]['status']!='SYNTHETIC_REVIEW_PASS']) for key,label,keys in GROUPS]
    common=[row['field'] for row in fields if not row['field'].startswith('TLS_')]
    options=[dict(id=key,label=label,required_fields=required,
        missing_fields=[k for k in required if by_key[k]['status']!='SYNTHETIC_REVIEW_PASS'],
        status=status,approved=False,connection_allowed=False) for key,label,required,status in (
          ('A','API-SSL 8729',common+[row['field'] for row in fields if row['field'].startswith('TLS_')],'NO_GO_APPROVAL_AND_LIVE_VERIFICATION_REQUIRED'),
          ('B','API 8728 üzerinden IPsec',common,'BLOCKED_BY_CURRENT_TLS_CONTRACT'))]
    return dict(version=VERSION,evidence_rule_version=RULE_VERSION,decision='NO_GO',connection='NOT CONNECTED',approval='APPROVAL REQUIRED',
        operator_approval='NOT_RECORDED',execution_authority='DENIED',network_enabled=False,connection_allowed=False,
        account_creation_allowed=False,polling=False,automatic_retry=False,live_verification=False,
        synthetic_checklist_complete=all(row['status']=='SYNTHETIC_REVIEW_PASS' for row in fields),
        contract=contract.model_dump(mode='json'),forbidden_policies=list(FORBIDDEN_POLICIES),packet_sha256=packet,
        groups=groups,evidence_fields=fields,transport_options=options,missing_evidence=[row['field'] for row in fields if row['status']!='SYNTHETIC_REVIEW_PASS'],
        current_transport_contract=AccessPlan().transport,account_status='NOT_CREATED_NOT_VERIFIED',minimum_privilege_status='ROS6_LAB_NOT_VERIFIED',
        manual_observations_promoted=False,proof_intake='SYNTHETIC_OFFLINE_TEST_ONLY_NO_UPLOAD',
        stop_conditions=['WRONG_IDENTITY','UNEXPECTED_WRITE','TLS_OR_IPSEC_UNVERIFIED','SOURCE_MISMATCH','V1_IMPACT','AUDIT_OR_ROLLBACK_MISSING'])
