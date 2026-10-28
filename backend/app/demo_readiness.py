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


def connection_reason(failure):
    reason=getattr(failure,'reason',failure)
    code=getattr(reason,'errno',None)
    if isinstance(reason,ConnectionRefusedError) or code==errno.ECONNREFUSED:
        return APIStatus('ABSENT', '127.0.0.1:8000 bağlantısı reddedildi: API çalışmıyor veya bu WSL ortamında dinlemiyor.')
    if isinstance(reason,PermissionError) or code in (errno.EPERM,errno.EACCES):
        return APIStatus('BLOCKED','Loopback erişimi izin/sandbox engeline takıldı; otomatik tekrar yapılmadı.')
    if isinstance(reason,TimeoutError):
        return APIStatus('BLOCKED','API zaman aşımı: servis meşgul veya erişim engelli; başka süreç başlatılmadı.')
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


def wait_ready(alive,timeout=12,probe=probe_api,clock=time.monotonic,sleep=time.sleep):
    deadline=clock()+timeout
    while True:
        if not alive():
            return APIStatus('BLOCKED','Yeni API süreci hazır olmadan kapandı; api.log dosyasını inceleyin.')
        status=probe()
        if status.state!='ABSENT':
            return status  # Permission, timeout and wrong-service failures are never retried.
        if clock()>=deadline:
            return APIStatus('BLOCKED','Yeni API 12 saniyelik hazır olma sınırında yanıt vermedi; api.log dosyasını inceleyin.')
        sleep(0.2)


def require_api_ready():
    status=probe_api()
    if status.state!='READY':
        from app.demo_repair import RepairBlocked
        raise RepairBlocked(status.detail+' Tek yerel başlatma+kabul komutu: ./dev.sh --accept-demo')
    return status


def main(argv=None):
    parser=argparse.ArgumentParser(description='Yalnız V2 HTTP hazır kontrolü; DB erişimi yok.')
    parser.add_argument('--wait',action='store_true')
    parser.add_argument('--pid',type=int)
    args=parser.parse_args(argv)
    if args.wait:
        if not args.pid or args.pid<=0:parser.error('--wait için geçerli --pid gerekli')
        def alive():
            try:os.kill(args.pid,0);return True
            except OSError:return False
        status=wait_ready(alive)
    else:status=probe_api()
    print(status.state+': '+status.detail,flush=True)
    return 0 if status.state=='READY' else 1


if __name__=='__main__':raise SystemExit(main())
