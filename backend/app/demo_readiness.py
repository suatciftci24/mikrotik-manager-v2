"""Bounded loopback readiness probe, independent of DB and thread-worker health checks."""
import argparse
from dataclasses import dataclass
import errno
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

API_BASE='http://127.0.0.1:8000'


@dataclass(frozen=True)
class APIStatus:
    state: str
    detail: str


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('API yönlendirmesi reddedildi.')


def connection_reason(failure,target='127.0.0.1:8000'):
    reason=getattr(failure,'reason',failure)
    code=getattr(reason,'errno',None)
    if isinstance(reason,ConnectionRefusedError) or code==errno.ECONNREFUSED:
        return APIStatus('ABSENT', f'{target} bağlantısı reddedildi: yerel V2 süreç bu WSL ortamında dinlemiyor.')
    if isinstance(reason,PermissionError) or code in (errno.EPERM,errno.EACCES):
        return APIStatus('BLOCKED','Loopback erişimi izin/sandbox engeline takıldı; otomatik tekrar yapılmadı.')
    if isinstance(reason,TimeoutError):
        return APIStatus('BLOCKED','Yerel HTTP zaman aşımı: servis meşgul veya erişim engelli; başka süreç başlatılmadı.')
    return APIStatus('BLOCKED','Loopback HTTP erişimi kurulamadı; ağ hatası ayrıntısı yok. Normal WSL ortamını kontrol edin.')


def probe_api(opener=None):
    client=opener or build_opener(ProxyHandler({}),NoRedirect())
    try:
        with client.open(Request(API_BASE+'/api/ready'),timeout=1) as response:
            payload=json.loads(response.read())
        if (payload.get('service')=='mikrotik-manager-v2' and payload.get('environment')=='local-demo'
                and payload.get('api_version')=='v1' and payload.get('database_checked') is False):
            return APIStatus('READY','Yerel V2 HTTP hazır; DB sağlığı henüz kontrol edilmedi.')
        return APIStatus('WRONG','Port 8000 yanıt veriyor fakat V2 hazır kimliği doğrulanamadı; mevcut servise dokunulmadı.')
    except HTTPError as failure:
        return APIStatus('WRONG',f'Port 8000 HTTP {failure.code} verdi. Eski V2 sürümü veya başka servis olabilir; yalnız kendi V2 dev.sh oturumunuzu kontrol edin.')
    except (URLError,OSError) as failure:
        return connection_reason(failure)
    except (ValueError,TypeError,AttributeError):
        return APIStatus('WRONG','Port 8000 V2 hazır sözleşmesini sağlamıyor; yönlendirme/farklı yanıt reddedildi.')


def probe_ui(opener=None):
    client=opener or build_opener(ProxyHandler({}),NoRedirect())
    try:
        with client.open(Request('http://127.0.0.1:5173/'),timeout=1) as response:
            body=response.read()
        if b'MikroTik Manager V2' in body and b'/src/main.tsx' in body:
            return APIStatus('READY','Yerel V2 Vite UI hazır.')
        return APIStatus('WRONG','Port 5173 V2 Vite UI kimliğini sağlamıyor; mevcut servise dokunulmadı.')
    except HTTPError as failure:
        return APIStatus('WRONG',f'UI portu HTTP {failure.code} verdi; mevcut servis değiştirilmedi.')
    except (URLError,OSError) as failure:
        return connection_reason(failure,'127.0.0.1:5173')
    except (ValueError,TypeError):
        return APIStatus('WRONG','UI yanıtı veya yönlendirmesi reddedildi.')


def wait_ready(alive,timeout=12,probe=probe_api,clock=time.monotonic,sleep=time.sleep,label='API'):
    deadline=clock()+timeout
    while True:
        if not alive():
            return APIStatus('BLOCKED',f'Yeni {label} süreci hazır olmadan kapandı; {label.lower()}.log dosyasını inceleyin.')
        status=probe()
        if status.state!='ABSENT':
            return status  # Permission, timeout and wrong-service failures are never retried.
        if clock()>=deadline:
            return APIStatus('BLOCKED',f'Yeni {label} hazır olma sınırında yanıt vermedi; {label.lower()}.log dosyasını inceleyin.')
        sleep(0.2)


def require_api_ready():
    status=probe_api()
    if status.state!='READY':
        from app.demo_repair import RepairBlocked
        raise RepairBlocked(status.detail+' Tek yerel başlatma+kabul komutu: ./dev.sh --accept-demo')
    return status


def main(argv=None):
    parser=argparse.ArgumentParser(description='Yalnız V2 HTTP hazır kontrolü; DB erişimi yok.')
    parser.add_argument('--ui',action='store_true',help='Mevcut Vite UI kimliği ve 5173 portunu kontrol et.')
    parser.add_argument('--wait',action='store_true')
    parser.add_argument('--pid',type=int)
    args=parser.parse_args(argv)
    probe=probe_ui if args.ui else probe_api
    if args.wait:
        if not args.pid or args.pid<=0:parser.error('--wait için geçerli --pid gerekli')
        def alive():
            try:os.kill(args.pid,0);return True
            except OSError:return False
        status=wait_ready(alive,probe=probe,label='UI' if args.ui else 'API')
    else:status=probe()
    print(status.state+': '+status.detail,flush=True)
    return 0 if status.state=='READY' else 1


if __name__=='__main__':raise SystemExit(main())
