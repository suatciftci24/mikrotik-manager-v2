"""Reusable, bounded RouterOS 6.49.x / 7.x metadata probe. No writes/retries/polling."""
from dataclasses import dataclass
from ipaddress import IPv4Address,IPv4Network
import hashlib
import hmac
import os
import re
import socket
import ssl
import time
from app.adapters.cebeci_api_ssl import ApiSslStop,_Wire
from app.integrations.cebeci_access import ReadIntent,verified_tls_context


@dataclass(frozen=True)
class ConnectionPolicy:
    enabled: bool=False
    source_ip: str=''
    allowed_networks: tuple[str,...]=()
    allowed_ports: tuple[int,...]=(8729,)

    @classmethod
    def environment(cls):
        try:
            enabled=os.environ.get('V2_ROUTER_ONBOARDING_ENABLED','false')
            if enabled not in ('true','false'):raise ValueError()
            return cls(enabled=='true',os.environ.get('V2_ROUTER_ONBOARDING_SOURCE_IP',''),
                tuple(filter(None,os.environ.get('V2_ROUTER_ONBOARDING_ALLOWED_CIDRS','').split(','))),
                tuple(int(p) for p in os.environ.get('V2_ROUTER_ONBOARDING_ALLOWED_PORTS','8729').split(',')))
        except (ValueError,TypeError):raise ApiSslStop('CONNECTION_POLICY_INVALID') from None

    def validate(self,address,port):
        if not self.enabled:raise ApiSslStop('ONBOARDING_CONNECTION_DISABLED')
        try:
            ip=IPv4Address(address);source=IPv4Address(self.source_ip)
            networks=tuple(IPv4Network(n.strip(),strict=True) for n in self.allowed_networks)
            forbidden=lambda a:a.is_loopback or a.is_link_local or a.is_multicast or a.is_unspecified or a.is_reserved or int(a)==0xFFFFFFFF
            if forbidden(ip) or forbidden(source) or not networks or any(n.prefixlen==0 for n in networks):raise ValueError()
            if not any(ip in n for n in networks) or port not in self.allowed_ports or port==8728 or not 1024<=port<=65535:raise ValueError()
        except (ValueError,TypeError):raise ApiSslStop('TARGET_OR_SOURCE_NOT_ALLOWED') from None


@dataclass(frozen=True)
class Target:
    address: str
    port: int
    ca_pem: str
    leaf_sha256: str
    expected_identity: str=''
    expected_version: str=''
    expected_model: str=''


class RouterApiSslClient:
    def probe(self,target:Target,credentials:tuple[str,str],policy:ConnectionPolicy):
        policy.validate(target.address,target.port)
        if not re.fullmatch('[a-f0-9]{64}',target.leaf_sha256):raise ApiSslStop('CERTIFICATE_PIN_REQUIRED')
        try:context=verified_tls_context(target.ca_pem)
        except ValueError:raise ApiSslStop('CA_CERTIFICATE_REJECTED') from None
        if context.verify_mode!=ssl.CERT_REQUIRED or context.check_hostname is not True or context.minimum_version<ssl.TLSVersion.TLSv1_2 or context.hostname_checks_common_name is not False:
            raise ApiSslStop('TLS_POLICY_REJECTED')
        raw=None;secure=None;deadline=time.monotonic()+10
        try:
            raw=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            raw.settimeout(2);raw.bind((policy.source_ip,0));raw.connect((target.address,target.port))
            remaining=deadline-time.monotonic()
            if remaining<=0:raise ApiSslStop('DEADLINE_EXCEEDED')
            raw.settimeout(min(2,remaining))
            secure=context.wrap_socket(raw,server_hostname=target.address)
            if secure.getpeername()[:2]!=(target.address,target.port) or secure.getsockname()[0]!=policy.source_ip:raise ApiSslStop('ENDPOINT_OR_SOURCE_MISMATCH')
            if secure.version() not in ('TLSv1.2','TLSv1.3'):raise ApiSslStop('TLS_POLICY_REJECTED')
            der=secure.getpeercert(binary_form=True)
            if not der or not hmac.compare_digest(hashlib.sha256(der).hexdigest(),target.leaf_sha256):raise ApiSslStop('CERTIFICATE_PIN_MISMATCH')
            if ('IP Address',target.address) not in secure.getpeercert().get('subjectAltName',()):raise ApiSslStop('CERTIFICATE_SAN_MISMATCH')
            wire=_Wire(secure,deadline,2);wire.login(credentials=credentials)
            identity=wire.read(ReadIntent(menu='/system/identity',properties=('name',)))
            if len(identity)!=1 or not identity[0]['name'].strip() or len(identity[0]['name'])>120:raise ApiSslStop('ROUTER_IDENTITY_REJECTED')
            if target.expected_identity and identity[0]['name']!=target.expected_identity:raise ApiSslStop('ROUTER_IDENTITY_MISMATCH')
            resource=wire.read(ReadIntent(menu='/system/resource',properties=('board-name','version')))
            if len(resource)!=1 or not resource[0]['board-name'].strip() or len(resource[0]['board-name'])>80:raise ApiSslStop('ROUTER_MODEL_REJECTED')
            if target.expected_model and resource[0]['board-name']!=target.expected_model:raise ApiSslStop('ROUTER_MODEL_MISMATCH')
            version=resource[0]['version']
            if not re.fullmatch(r'(?:6\.49\.\d+|7\.\d+(?:\.\d+)?(?:beta\d+|rc\d+)?)(?: \((?:stable|long-term|testing|development)\))?',version):raise ApiSslStop('ROUTEROS_VERSION_UNSUPPORTED')
            if target.expected_version and version.removesuffix(' (stable)')!=target.expected_version.removesuffix(' (stable)'):raise ApiSslStop('ROUTEROS_VERSION_MISMATCH')
            if any(credentials[1] in value for row in (identity[0],resource[0]) for value in row.values()):raise ApiSslStop('SENSITIVE_METADATA_REJECTED')
            wire.timeout()
            return dict(identity=identity[0]['name'],model=resource[0]['board-name'],routeros_version=version)
        except ApiSslStop:raise
        except ssl.SSLError:raise ApiSslStop('TLS_VERIFICATION_FAILED') from None
        except TimeoutError:raise ApiSslStop('CONNECTION_TIMEOUT') from None
        except Exception:raise ApiSslStop('API_SSL_STOP') from None
        finally:
            for stream in (secure,raw):
                if stream is not None:
                    try:stream.close()
                    except Exception:pass
