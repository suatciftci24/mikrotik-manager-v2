"""Bounded local health checks only; no device connections, DSNs or process guesses."""
from datetime import datetime,timezone
from threading import Lock
from app.services import demo_subscriptions
from app.core.config import settings
from app.core.security import SESSION_TIMEOUT_SECONDS
_last={};_lock=Lock()

def security_policy():
    return dict(read_only=True,session_timeout_seconds=SESSION_TIMEOUT_SECONDS,cookie_http_only=True,cookie_same_site='strict',cookie_secure=settings.session_secure,
        csrf='SameSite Strict + JSON + işlem başlığı + backend yetki denetimi',revocation='Yetkiler her istekte DB’den okunur; logout mevcut süreçteki tokenı iptal eder.',
        failed_login='Hatalı/bilinmeyen/pasif giriş aynı 401 sonucudur. Otomatik hesap kilitleme veya rate-limit uygulanmıyor; bu ekrandan yapılandırılamaz.',password_hash='scrypt; salt ve hash yanıtlanmaz')

def sources():
    return dict(mode='DEMO / SYNTHETIC',router='DISCONNECTED',radius='DISCONNECTED',v1='DISCONNECTED',
                evidence='Bu V2 uygulamasında canlı adaptör yapılandırması yok; yalnız izole yerel demo depo/projeksiyonları kullanılır.',is_demo=True)

def health():
    now=datetime.now(timezone.utc).isoformat()
    checks={}
    with _lock:
        _last['api']=now
        checks['api']=dict(status='UP',checked_at=now,last_success=now,error=None)
    try:
        connected=bool(demo_subscriptions.store.ping())
        if not connected:raise demo_subscriptions.DemoStorageUnavailable()
        with _lock:_last['database']=now
        database=dict(status='UP',checked_at=now,last_success=now,error=None)
    except demo_subscriptions.DemoStorageUnavailable:
        with _lock:previous=_last.get('database')
        database=dict(status='ERROR',checked_at=now,last_success=previous,error='V2 veritabanı/marker kontrolü tamamlanamadı; bağlantı ayrıntıları gizlendi.')
    checks['database']=database
    for key in ('ui','proxy','postgres_process','vite_process'):
        checks[key]=dict(status='UNKNOWN',checked_at=None,last_success=None,error='Bu bileşen için sunucu süreç ölçümü yok. UI/proxy istemcide ayrıca kontrol edilir.')
    return dict(checks=checks,sources=sources(),is_demo=True,scope='Son başarılı kontrol yalnız bu API sürecinin gözlemidir; restart sonrası bilinmiyor.')
