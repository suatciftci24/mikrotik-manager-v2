"""Clearly marked, in-memory Phase 1 data. Never writes to PostgreSQL or devices."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# Explicit synthetic expiry dates relative to local demo startup; never inferred from joined_at.
DEMO_DATE = datetime.now(ZoneInfo("Europe/Istanbul")).date()

def demo_expiry(days: int | None) -> str | None:
    return (DEMO_DATE + timedelta(days=days)).isoformat() if days is not None else None


STAMP = datetime(2026, 10, 26, 9, 42, tzinfo=timezone.utc).isoformat()
ROUTERS = [
    {'id': 'demo-router-001', 'name': 'Kadıköy · Merkez', 'management_address': '192.0.2.11',
     'site': 'İstanbul Anadolu', 'model': 'CCR2004-16G-2S+', 'routeros_version': '7.16.2',
     'status': 'ONLINE', 'cpu_percent': 24, 'memory_percent': 61, 'subscriber_count': 248,
     'uptime': '38g 14s', 'last_seen': STAMP, 'is_demo': True},
    {'id': 'demo-router-002', 'name': 'Ataşehir · Doğu', 'management_address': '192.0.2.22',
     'site': 'İstanbul Anadolu', 'model': 'RB5009UG+S+', 'routeros_version': '7.16.2',
     'status': 'ONLINE', 'cpu_percent': 38, 'memory_percent': 47, 'subscriber_count': 176,
     'uptime': '21g 6s', 'last_seen': STAMP, 'is_demo': True},
    {'id': 'demo-router-003', 'name': 'Üsküdar · Sahil', 'management_address': '192.0.2.33',
     'site': 'İstanbul Anadolu', 'model': 'CCR1009-7G-1C-1S+', 'routeros_version': '7.15.3',
     'status': 'DEGRADED', 'cpu_percent': 72, 'memory_percent': 78, 'subscriber_count': 94,
     'uptime': '9g 2s', 'last_seen': STAMP, 'is_demo': True},
    {'id': 'demo-router-004', 'name': 'Kartal · Güney', 'management_address': '192.0.2.44',
     'site': 'İstanbul Anadolu', 'model': 'hEX S', 'routeros_version': '7.16.2',
     'status': 'ONLINE', 'cpu_percent': 17, 'memory_percent': 55, 'subscriber_count': 131,
     'uptime': '64g 1s', 'last_seen': STAMP, 'is_demo': True},
]

SUBSCRIBERS = [
    {'id': 'demo-sub-1001', 'username': 'ayse.demir', 'customer_name': 'Ayşe Demir', 'router_name': 'Kadıköy · Merkez',
     'plan': 'Fiber 100', 'source': 'LOCAL', 'status': 'ACTIVE', 'monthly_price': 549.90,
     'ip_address': '100.64.12.41', 'joined_at': '2025-04-12', 'expires_on': demo_expiry(-3), 'last_seen': STAMP, 'is_demo': True},
    {'id': 'demo-sub-1002', 'username': 'mert.kaya', 'customer_name': 'Mert Kaya', 'router_name': 'Ataşehir · Doğu',
     'plan': 'Fiber 500', 'source': 'RADIUS', 'status': 'ACTIVE', 'monthly_price': 849.90,
     'ip_address': '100.64.18.26', 'joined_at': '2024-11-03', 'expires_on': demo_expiry(5), 'last_seen': STAMP, 'is_demo': True},
    {'id': 'demo-sub-1003', 'username': 'selin.yilmaz', 'customer_name': 'Selin Yılmaz', 'router_name': 'Üsküdar · Sahil',
     'plan': 'Fiber 100', 'source': 'LOCAL', 'status': 'PAUSED', 'monthly_price': 549.90,
     'ip_address': '—', 'joined_at': '2025-01-19', 'expires_on': demo_expiry(20), 'last_seen': None, 'is_demo': True},
    {'id': 'demo-sub-1004', 'username': 'burak.arslan', 'customer_name': 'Burak Arslan', 'router_name': 'Kartal · Güney',
     'plan': 'Fiber 50', 'source': 'RADIUS', 'status': 'ACTIVE', 'monthly_price': 429.90,
     'ip_address': '100.64.31.18', 'joined_at': '2026-02-22', 'expires_on': demo_expiry(60), 'last_seen': STAMP, 'is_demo': True},
    {'id': 'demo-sub-1005', 'username': 'deniz.celik', 'customer_name': 'Deniz Çelik', 'router_name': 'Kadıköy · Merkez',
     'plan': 'Fiber 1000', 'source': 'LOCAL', 'status': 'ACTIVE', 'monthly_price': 1249.90,
     'ip_address': '100.64.12.87', 'joined_at': '2024-07-14', 'expires_on': demo_expiry(0), 'last_seen': STAMP, 'is_demo': True},
    {'id': 'demo-sub-1006', 'username': 'eda.oz', 'customer_name': 'Eda Öz', 'router_name': 'Ataşehir · Doğu',
     'plan': 'Fiber 100', 'source': None, 'status': 'PENDING', 'monthly_price': 549.90,
     'ip_address': '—', 'joined_at': '2026-10-25', 'expires_on': demo_expiry(None), 'last_seen': None, 'is_demo': True},
    {'id': 'demo-sub-1007', 'username': 'onur.akin', 'customer_name': 'Onur Akın', 'router_name': 'Üsküdar · Sahil',
     'plan': 'Fiber 50', 'source': 'RADIUS', 'status': 'ACTIVE', 'monthly_price': 429.90,
     'ip_address': '100.64.25.63', 'joined_at': '2025-08-29', 'expires_on': demo_expiry(30), 'last_seen': STAMP, 'is_demo': True},
]

DASHBOARD = {
    'summary': {'router_count': 4, 'routers_online': 3, 'subscribers_total': 649,
                'subscribers_online': 555, 'radius_accounts': 286, 'local_accounts': 363,
                'monthly_revenue': 382440, 'attention_count': 1},
    'traffic': [36, 42, 39, 48, 45, 55, 51, 64, 58, 71, 67, 76],
    'activity': [
        {'title': 'Yeni abonelik oluşturuldu', 'detail': 'Fiber 100 · demo-sub-1006', 'time': '10:12', 'kind': 'subscriber'},
        {'title': 'RADIUS kimliği doğrulandı', 'detail': 'Ataşehir · Doğu', 'time': '09:48', 'kind': 'radius'},
        {'title': 'Router telemetrisi yenilendi', 'detail': 'Kadıköy · Merkez', 'time': '09:42', 'kind': 'router'},
    ],
    'attention': {'router_id': 'demo-router-003', 'message': 'CPU kullanımı yükseliyor', 'value': 72},
    'is_demo': True,
}
