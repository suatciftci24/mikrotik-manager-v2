"""Offline-only single-candidate security contract. No transport, resolver or live evidence intake."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from ipaddress import IPv4Address, IPv4Network
import json
from types import MappingProxyType
from typing import Literal, Protocol
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from fastapi import HTTPException
from app.integrations.cebeci_preparation import CANDIDATE, READ_FIELDS, authorize, project_fixture_row

# Immutable narrowed copy. Credential-bearing menus and ALL live IPsec SA/peer sources are excluded.
READ_SCOPE = MappingProxyType({menu:tuple(field for field in READ_FIELDS[menu] if menu!='/ppp/active' or field!='name') for menu in (
    '/system/identity','/system/resource','/interface','/ip/route','/ppp/active')})
POLICY_VERSION='CEBECI_CLOSED_ACCESS_V1'
REQUIREMENTS = {
 'IDENTITY': ('Tek router identity', 'Güncel CEBECI_TOWERS exact identity kanıtı.'),
 'MODEL': ('Model eşleşmesi', 'RB3011UiAS exact model; alias varsayılmaz.'),
 'VERSION': ('RouterOS 6 build', '6.49.19 tam build ve istemci uyumu için ayrı lab incelemesi.'),
 'MANAGEMENT_ADDRESS': ('Yönetim adresi eşleşmesi', 'Geçmiş adres endpoint değildir; ayrı incelenmiş tek cihaz pin eşleşmesi.'),
 'ROUTER_PERMISSION': ('Cihaz yetkisi', 'Ayrı kayıt ve can_view/can_view_reports; demo ADMIN grantleri yeterli değildir.'),
 'NETWORK_PATH': ('Ağ yolu', 'Manuel incelenmiş tek hedef/port/yol; bu aşamada ping veya bağlantı yok.'),
 'SOURCE_ALLOWLIST': ('İzinli kaynak', 'Cihazın gördüğü /32; hesap, servis ve firewall kaynak sınırlarının birlikte kanıtı.'),
 'TLS': ('TLS protokol/istemci', 'TLS 1.2+ doğrulanmış uyumluluk; anonymous DH, plain API ve fallback yasak.'),
 'CERTIFICATE_CHAIN': ('Sertifika güven zinciri', 'Güvenilen CA zinciri; leaf tek başına veya fingerprint tek başına yeterli değil.'),
 'CERTIFICATE_NAME': ('Sertifika isim eşleşmesi', 'Doğrulanmış hedef SAN/IP adı; hostname kontrolü atlanamaz.'),
 'CERTIFICATE_PIN': ('Sertifika public fingerprint', 'Ayrı incelenmiş public SHA-256 pin eşleşmesi; özel anahtar alınmaz.'),
 'CERTIFICATE_VALIDITY': ('Sertifika geçerliliği', 'Zaman, kullanım ve iptal durumu incelemesi; başarısız/eksik kanıt STOP.'),
 'AUTHENTICATION': ('Ayrı pilot hesabı', 'ADMIN/V1 hesabı değil; yerel kimlik ve auth incelemesi. Parola/reference alınmaz.'),
 'MINIMUM_PRIVILEGE': ('Minimum yetki', 'Yalnız aday read,api özel grubu ve gerçek ROS6 davranışı lab kanıtı; read güvenli varsayılmaz.'),
 'ROS6_FIELD_LAB': ('Alan ve yan etki lab kontrolü', 'İzinli menü/alan ve dosya/policy sınırları tam ROS6 build üzerinde doğrulanmalı.'),
 'FRESHNESS': ('Kaynak güncelliği', 'UTC-aware kaynak zamanı; eksik/gelecek UNKNOWN, beş dakikadan eski STALE.'),
 'V1_ISOLATION': ('V1 izolasyonu', 'V1 etkisi olmadığının baseline incelemesi; mevcut V1 sorgulanmaz veya değiştirilmez.'),
 'AUDIT': ('Redacted audit hazırlığı', 'Sabit kod/aday/policy hash/zaman; credential veya ham SA/response kaydı yok.'),
 'STOP_OWNER': ('STOP sorumluluğu', 'Süre/kayıt bütçesi, sorumlu ve yeniden denememe prosedürü tanımlı.'),
}


class ClosedContract(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True,hide_input_in_errors=True)


class AccessPlan(ClosedContract):
    candidate_id:Literal['CEBECI_TOWERS']=CANDIDATE
    expected_identity:Literal['CEBECI_TOWERS']=CANDIDATE
    expected_model:Literal['RB3011UiAS']='RB3011UiAS'
    expected_version:Literal['6.49.19']='6.49.19'
    # Optional reviewed pin only; NEVER a connect_host or an automatically bound historical endpoint.
    reviewed_management_pin:Literal['10.250.0.19']|None=None
    reviewed_source_cidr:str|None=None
    public_certificate_sha256:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    transport:Literal['API_SSL']='API_SSL'
    port:Literal[8729]=8729
    tls_minimum:Literal['TLSv1.2']='TLSv1.2'
    network_enabled:StrictBool=False
    verify_tls:StrictBool=True
    verify_hostname:StrictBool=True
    polling:StrictBool=False
    automatic_retry:StrictBool=False
    credential_storage:Literal['NONE']='NONE'
    @field_validator('network_enabled','polling','automatic_retry')
    @classmethod
    def closed(cls,value):
        if value is not False:raise ValueError('PILOT_MUST_REMAIN_DISABLED')
        return value
    @field_validator('verify_tls','verify_hostname')
    @classmethod
    def required_verification(cls,value):
        if value is not True:raise ValueError('VERIFICATION_BYPASS_FORBIDDEN')
        return value
    @field_validator('reviewed_source_cidr')
    @classmethod
    def single_source(cls,value):
        if value is not None:
            network=IPv4Network(value,strict=True)
            if (network.prefixlen!=32 or str(network)!=value or network.network_address.is_unspecified or network.network_address.is_multicast or network.network_address.is_loopback or network.network_address.is_link_local or str(network.network_address)=='255.255.255.255'):
                raise ValueError('EXACT_REVIEWED_UNICAST_SOURCE_REQUIRED')
        return value


class OfflineEvidence(ClosedContract):
    source:Literal['OFFLINE_UNVERIFIED','SYNTHETIC_FIXTURE']='OFFLINE_UNVERIFIED'
    observed_identity:str|None=Field(default=None,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    observed_model:str|None=Field(default=None,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    observed_version:str|None=Field(default=None,pattern=r'^\d{1,2}\.\d{1,2}\.\d{1,3}$')
    observed_management_address:IPv4Address|None=None
    observed_source_address:IPv4Address|None=None
    public_certificate_sha256:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    observed_at:datetime|None=None
    policies:tuple[str,...]|None=Field(default=None,max_length=32)
    tls_version:Literal['TLSv1.2','TLSv1.3','LEGACY']|None=None
    router_view_granted:StrictBool|None=None
    router_reports_granted:StrictBool|None=None
    network_path_reviewed:StrictBool|None=None
    account_source_restricted:StrictBool|None=None
    service_source_restricted:StrictBool|None=None
    firewall_source_restricted:StrictBool|None=None
    tls_verified:StrictBool|None=None
    chain_verified:StrictBool|None=None
    hostname_verified:StrictBool|None=None
    certificate_validity_reviewed:StrictBool|None=None
    separate_account_reviewed:StrictBool|None=None
    authentication_reviewed:StrictBool|None=None
    minimum_privilege_lab_verified:StrictBool|None=None
    ros6_fields_lab_verified:StrictBool|None=None
    v1_isolation_reviewed:StrictBool|None=None
    v1_impact_detected:StrictBool|None=None
    audit_redaction_reviewed:StrictBool|None=None
    audit_baseline_reviewed:StrictBool|None=None
    stop_owner_and_budget_reviewed:StrictBool|None=None
    @field_validator('observed_at',mode='before')
    @classmethod
    def timestamp_type(cls,value):
        if value is not None and not isinstance(value,(str,datetime)):raise ValueError('EXPLICIT_EVIDENCE_TIME_REQUIRED')
        return value
    @field_validator('observed_at')
    @classmethod
    def aware(cls,value):
        if value is not None and value.utcoffset() is None:raise ValueError('AWARE_EVIDENCE_CLOCK_REQUIRED')
        return value.astimezone(timezone.utc) if value else None
    @field_validator('policies')
    @classmethod
    def safe_policy_names(cls,value):
        if value is not None and (len(value)!=len(set(value)) or any(not p.isascii() or not p.replace('-','').isalpha() or len(p)>24 for p in value)):
            raise ValueError('INVALID_POLICY_DESCRIPTOR')
        return value


class ReadIntent(ClosedContract):
    menu:Literal['/system/identity','/system/resource','/interface','/ip/route','/ppp/active']
    operation:Literal['print']='print'
    properties:tuple[str,...]=Field(min_length=1,max_length=8)
    @model_validator(mode='after')
    def explicit_fields(self):
        if len(self.properties)!=len(set(self.properties)) or set(self.properties)-set(READ_SCOPE[self.menu]):
            raise ValueError('OUTSIDE_PILOT_READ_BOUNDARY')
        return self


class PilotReadAdapter(Protocol):
    """Future narrow capability only; broad RouterOSAdapter mutation methods must never be injected."""
    def read_metadata(self,intent:ReadIntent)->tuple[dict,...]:...


def project_synthetic_metadata(intent:ReadIntent,row:dict,*,source='SYNTHETIC_FIXTURE'):
    # Check provenance BEFORE inspecting a row. No live SA/intake/credential persistence exists.
    if source!='SYNTHETIC_FIXTURE':raise ValueError('LIVE_DATA_INTAKE_DISABLED')
    intent=ReadIntent.model_validate(intent.model_dump(mode='json'))
    if type(row) is not dict:raise ValueError('UNEXPECTED_ROW_TYPE')
    sensitive={'password','auth-key','enc-key','secret','psk','private-key','preshared-key','passphrase','secretref','token','api-key'}
    if any(str(key).lower().replace('_','-') in sensitive for key in row):raise ValueError('SENSITIVE_FIELD_RETURNED')
    if set(row)-set(intent.properties):raise ValueError('UNEXPECTED_FIELD_RETURNED')
    safe=project_fixture_row(intent.menu,row)
    if set(row)-set(safe):raise ValueError('UNSAFE_OR_UNSUPPORTED_FIELD_VALUE')
    return {key:safe[key] for key in intent.properties if key in safe}


def dispatch_pilot_read(user,plan:AccessPlan,evidence:OfflineEvidence,intent:ReadIntent,adapter:PilotReadAdapter):
    # Before any adapter attribute access. Current full-scope ADMIN is plan-view only.
    authorize(user,getattr(plan,'candidate_id',CANDIDATE),purpose='DEVICE_READ')
    # Defense if a future authorization implementation expands scope: phase 22 still cannot execute.
    raise HTTPException(403,'PILOT_NETWORK_DISABLED_APPROVAL_REQUIRED')


def assess(user,plan:AccessPlan|None=None,evidence:OfflineEvidence|None=None,*,now:datetime|None=None):
    authorize(user)
    try:
        plan=AccessPlan.model_validate((plan or AccessPlan()).model_dump(mode='json'))
        evidence=OfflineEvidence.model_validate((evidence or OfflineEvidence()).model_dump(mode='json'))
    except ValueError:
        raise ValueError('PILOT_CONTRACT_REJECTED') from None
    now=now or datetime.now(timezone.utc)
    if now.utcoffset() is None:raise ValueError('AWARE_ASSESSMENT_CLOCK_REQUIRED')
    age='UNKNOWN' if evidence.observed_at is None or evidence.observed_at>now else 'STALE' if now-evidence.observed_at>timedelta(minutes=5) else 'PASS'
    def status(*values):
        if any(value is False for value in values):return 'BLOCKED'
        if any(value is None for value in values):return 'UNKNOWN'
        return age
    def match(seen,expected):
        if seen is None or expected is None:return 'UNKNOWN'
        return age if str(seen)==str(expected) else 'BLOCKED'
    source_match=None if plan.reviewed_source_cidr is None or evidence.observed_source_address is None else evidence.observed_source_address in IPv4Network(plan.reviewed_source_cidr)
    policy_match=None if evidence.policies is None else set(evidence.policies)=={'read','api'}
    states={
      'IDENTITY':match(evidence.observed_identity,plan.expected_identity),
      'MODEL':match(evidence.observed_model,plan.expected_model),
      'VERSION':match(evidence.observed_version,plan.expected_version),
      'MANAGEMENT_ADDRESS':match(evidence.observed_management_address,plan.reviewed_management_pin),
      'ROUTER_PERMISSION':status(evidence.router_view_granted,evidence.router_reports_granted),
      'NETWORK_PATH':status(evidence.network_path_reviewed),
      'SOURCE_ALLOWLIST':status(source_match,evidence.account_source_restricted,evidence.service_source_restricted,evidence.firewall_source_restricted),
      'TLS':status(evidence.tls_verified,None if evidence.tls_version is None else evidence.tls_version in ('TLSv1.2','TLSv1.3')),
      'CERTIFICATE_CHAIN':status(evidence.chain_verified),
      'CERTIFICATE_NAME':status(evidence.hostname_verified),
      'CERTIFICATE_PIN':match(evidence.public_certificate_sha256,plan.public_certificate_sha256),
      'CERTIFICATE_VALIDITY':status(evidence.certificate_validity_reviewed),
      'AUTHENTICATION':status(evidence.separate_account_reviewed,evidence.authentication_reviewed),
      'MINIMUM_PRIVILEGE':status(policy_match,evidence.minimum_privilege_lab_verified),
      'ROS6_FIELD_LAB':status(evidence.ros6_fields_lab_verified),
      'FRESHNESS':age,
      'V1_ISOLATION':status(evidence.v1_isolation_reviewed,None if evidence.v1_impact_detected is None else not evidence.v1_impact_detected),
      'AUDIT':status(evidence.audit_redaction_reviewed,evidence.audit_baseline_reviewed),
      'STOP_OWNER':status(evidence.stop_owner_and_budget_reviewed),
    }
    checklist=[dict(criterion=key,label=label,status=states[key],reason_code=key+'_'+states[key],
                    evidence_required=required,source=evidence.source) for key,(label,required) in REQUIREMENTS.items()]
    checklist.append(dict(criterion='EXPLICIT_EXECUTION_APPROVAL',label='Ayrı gerçek bağlantı onayı',status='BLOCKED',
        reason_code='EXECUTION_NOT_AUTHORIZED',evidence_required='Bu faz onay almaz/saklamaz; ayrı açık kullanıcı onayı ve yeni yetki incelemesi gerekir.',source='SERVER_CLOSED_POLICY'))
    encoded=json.dumps([POLICY_VERSION,plan.model_dump(mode='json'),evidence.model_dump(mode='json'),dict(READ_SCOPE)],sort_keys=True,separators=(',',':'))
    return dict(policy_version=POLICY_VERSION,decision='NO_GO',plan_defined=True,
        offline_checklist_complete=all(state=='PASS' for state in states.values()),security_status='SECURITY NOT VERIFIED',
        connection='NOT CONNECTED',approval='APPROVAL REQUIRED',execution_authorized=False,connection_allowed=False,
        packet_digest=sha256(encoded.encode()).hexdigest(),configuration=plan.model_dump(mode='json'),
        checklist=checklist,blocking_findings=[dict(criterion=row['criterion'],status=row['status'],code=row['reason_code']) for row in checklist if row['status']!='PASS'],
        read_scope=[dict(menu=menu,properties=list(properties),operation='print',live_access=False) for menu,properties in READ_SCOPE.items()],
        excluded_sources=['/ppp/secret','/ip/ipsec/installed-sa','/ip/ipsec/active-peers','/certificate','/user','/file','/export','/system/script','/ip/firewall','/ip/firewall/nat'],
        stop_conditions=['IDENTITY_MODEL_VERSION_MISMATCH','MANAGEMENT_OR_SOURCE_MISMATCH','PERMISSION_MISMATCH','TLS_OR_CERTIFICATE_UNVERIFIED',
          'STALE_OR_UNKNOWN_EVIDENCE','UNEXPECTED_WRITE_ATTEMPT','LIVE_SA_OR_CREDENTIAL_INTAKE','V1_IMPACT','AUDIT_OR_TIMEBOX_UNVERIFIED'],
        audit_fields=['candidate_id','policy_version','packet_digest','criterion','fixed_reason_code','review_time'],
        raw_evidence_stored=False,live_observation_verified=False,secret_resolution=False,network_enabled=False,polling=False,automatic_retry=False)


def prepare_offline_tls_context(user,plan:AccessPlan|None=None,*,public_ca_pem:str|None=None):
    """Prepare a client verifier in memory only. Never connects, resolves, loads keys or authorizes IO.

    A reviewed plan/pin is metadata, not live verification. Future transport must separately
    enforce the public leaf pin after verified TLS and before credentials; dispatch stays 403.
    """
    authorize(user)
    try:plan=AccessPlan.model_validate(dict((plan or AccessPlan()).__dict__))
    except (ValueError,AttributeError):raise ValueError('PILOT_CONTRACT_REJECTED') from None
    if any(value is None for value in (plan.reviewed_management_pin,plan.reviewed_source_cidr,plan.public_certificate_sha256)):
        raise ValueError('REVIEWED_TARGET_SOURCE_AND_PUBLIC_PIN_REQUIRED')
    import re
    import ssl
    if not isinstance(public_ca_pem,str) or not 1<=len(public_ca_pem)<=262144:
        raise ValueError('PILOT_PUBLIC_CA_REQUIRED')
    public_ca_pem=public_ca_pem.replace('\r\n','\n').strip()
    # Only public CA certificates. Reject keys, DH params, file paths and mixed/raw payloads.
    if not re.fullmatch(r'(?:-----BEGIN CERTIFICATE-----\n[A-Za-z0-9+/=\n]+-----END CERTIFICATE-----\s*)+',public_ca_pem):
        raise ValueError('PILOT_PUBLIC_CA_REJECTED')
    count=public_ca_pem.count('-----BEGIN CERTIFICATE-----')
    if count>16:raise ValueError('PILOT_PUBLIC_CA_REJECTED')
    try:
        # Bare constructor deliberately avoids default/system trust and SSLKEYLOGFILE side effects.
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.verify_mode=ssl.CERT_REQUIRED
        context.check_hostname=True
        context.hostname_checks_common_name=False
        context.verify_flags|=ssl.VERIFY_X509_STRICT
        context.options|=ssl.OP_NO_COMPRESSION
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:!aNULL:!eNULL:!DSS:!MD5:!RC4:!3DES')
        context.load_verify_locations(cadata=public_ca_pem)
        # No leaf/non-CA or duplicate anchors in this dedicated trust input.
        if len(context.get_ca_certs())!=count:raise ValueError('CA_REQUIRED')
        return context
    except (ssl.SSLError,ValueError):raise ValueError('PILOT_PUBLIC_CA_REJECTED') from None
