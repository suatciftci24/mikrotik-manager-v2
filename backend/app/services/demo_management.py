"""Pure demo account rules. Never contacts RouterOS or FreeRADIUS."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.services.demo_data import ROUTERS, SUBSCRIBERS
from app.services.demo_subscriptions import DemoChangeError


def demo_plans():
    return [{'name': name, 'monthly_price': price} for name, price in sorted({r['plan']: r['monthly_price'] for r in SUBSCRIBERS}.items())]


def plan_price(name):
    plan = next((p for p in demo_plans() if p['name'] == name), None)
    if plan is None:
        raise DemoChangeError(422, 'Geçerli bir sentetik demo paketi seçin.')
    return plan['monthly_price']


def history_event(command, actor_id, source, operation, previous, values):
    return {'id': str(command.request_id), 'occurred_at': datetime.now(timezone.utc).isoformat(),
            'operation': operation, 'source': source, 'actor_id': actor_id, 'is_demo': True,
            'previous_values': previous, 'new_values': values}


def calculate_create(command, actor_id, items):
    router = next((r for r in ROUTERS if r['id'] == command.router_id and r['is_demo'] is True), None)
    if router is None:
        raise DemoChangeError(422, 'Geçerli bir sentetik router seçin.')
    price = plan_price(command.plan)
    today = datetime.now(ZoneInfo('Europe/Istanbul')).date()
    if command.expires_on is not None and command.expires_on < today:
        raise DemoChangeError(422, 'Bitiş tarihi Türkiye gününe göre geçmişte olamaz.')
    # Keep the domain router+username uniqueness, including cross-source conflicts.
    # RADIUS has a shared namespace; unknown authority cannot rule out a conflict.
    for row in items:
        if row['username'].strip().casefold() != command.username.casefold():
            continue
        if (row.get('router_id') == router['id'] or row['router_name'] == router['name'] or
                command.source == 'RADIUS' and row.get('source') not in ('LOCAL',)):
            raise DemoChangeError(409, 'Kullanıcı adı bu router veya ortak RADIUS kapsamında zaten kullanılıyor; belirsiz kaynaklar da çakışma sayılır.')
    item = {'id': 'demo-sub-' + str(command.request_id), 'username': command.username,
            'customer_name': command.customer_name, 'router_name': router['name'], 'router_id': router['id'],
            'plan': command.plan, 'monthly_price': price, 'source': command.source, 'status': command.status,
            'expires_on': command.expires_on.isoformat() if command.expires_on else None,
            'joined_at': today.isoformat(), 'ip_address': 'Veri yok', 'last_seen': None,
            'access_type': 'PPPOE', 'revision': 1, 'is_demo': True}
    values = {key: item[key] for key in ('username', 'customer_name', 'router_name', 'source', 'plan', 'monthly_price', 'status', 'expires_on', 'access_type')}
    return item, history_event(command, actor_id, command.source, 'CREATE', {}, values)


def calculate_management_change(item, command, actor_id):
    if not item:
        raise DemoChangeError(404, 'Kayıt bulunamadı')
    if item.get('is_demo') is not True:
        raise DemoChangeError(403, 'Yalnız sentetik demo kayıtları değiştirilebilir.')
    if item.get('source') not in ('LOCAL', 'RADIUS'):
        raise DemoChangeError(409, 'Kaynak bilinmiyor; değişiklik kapalı.')
    field = 'plan' if command.operation == 'PLAN_CHANGE' else 'status'
    if (item['revision'] != command.expected_revision or item['source'] != command.expected_source
            or item[field] != command.expected_value):
        raise DemoChangeError(409, 'Kayıt değişmiş. Güncel kaydı yeniden yükleyip onaylayın.')
    if command.value == item[field]:
        raise DemoChangeError(422, 'Yeni değer mevcut değerden farklı olmalıdır.')
    values = {field: command.value}
    previous = {field: item[field]}
    if field == 'plan':
        values['monthly_price'] = plan_price(command.value)
        previous['monthly_price'] = item['monthly_price']
    elif command.value not in ('ACTIVE', 'PAUSED'):
        raise DemoChangeError(422, 'Durum yalnız etkin veya devre dışı olabilir.')
    updated = {**item, **values, 'revision': item['revision'] + 1}
    return updated, history_event(command, actor_id, item['source'], command.operation, previous, values)
