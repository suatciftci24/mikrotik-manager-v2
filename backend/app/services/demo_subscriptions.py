"""Synthetic subscription service; validation is shared by memory and PostgreSQL adapters."""
from copy import deepcopy
from datetime import date, datetime, timezone, timedelta
from threading import RLock
from zoneinfo import ZoneInfo

from app.schemas.subscriber_events import ExpiryChange


class DemoChangeError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


class DemoStorageUnavailable(Exception):
    pass


def request_fingerprint(item_id, actor_id, change):
    import json
    return json.dumps([item_id, actor_id, change.model_dump_json()], separators=(',', ':'))


def calculate_change(item, change: ExpiryChange, actor_id: str, items=None):
    request_id = str(change.request_id)
    if hasattr(change, 'action'):
        return calculate_quick(item, change, actor_id, items)
    if not item:
        raise DemoChangeError(404, 'Kayıt bulunamadı')
    if item.get('is_demo') is not True:
        raise DemoChangeError(403, 'Yalnız sentetik demo kayıtları değiştirilebilir.')
    if item.get('source') not in ('LOCAL', 'RADIUS'):
        raise DemoChangeError(409, 'Kaynak bilinmiyor; kaynak doğrulanmadan değişiklik yapılamaz.')
    old = item.get('expires_on')
    expected = change.expected_expires_on.isoformat() if change.expected_expires_on else None
    if item['revision'] != change.expected_revision or old != expected or item['source'] != change.expected_source:
        raise DemoChangeError(409, 'Kayıt değişmiş. Güncel tarihi yeniden yükleyip onaylayın.')
    today = datetime.now(ZoneInfo('Europe/Istanbul')).date()
    if change.expires_on < today:
        raise DemoChangeError(422, 'Yeni bitiş tarihi Türkiye gününe göre geçmişte olamaz.')
    new = change.expires_on.isoformat()
    if new == old:
        raise DemoChangeError(422, 'Yeni bitiş tarihi mevcut tarihten farklı olmalıdır.')
    if change.operation == 'RENEWAL' and (old is None or change.expires_on <= date.fromisoformat(old)):
        raise DemoChangeError(422, 'Yenileme için mevcut bitiş tarihinden daha ileri bir tarih seçin.')
    updated = {**item, 'expires_on': new, 'revision': item['revision'] + 1}
    event = {'id': request_id, 'occurred_at': datetime.now(timezone.utc).isoformat(),
             'previous_expires_on': old, 'expires_on': new, 'operation': change.operation,
             'source': item['source'], 'actor_id': actor_id, 'is_demo': True}
    return updated, event


class DemoSubscriptionStore:
    def __init__(self, rows):
        self._lock = RLock()
        self._state = ({row['id']: {**deepcopy(row), 'revision': 0} for row in rows}, {}, {})

    def list_items(self):
        with self._lock:
            return deepcopy(list(self._state[0].values()))

    def detail(self, item_id):
        with self._lock:
            items, history, _ = self._state
            item = items.get(item_id)
            return deepcopy({'item': item, 'history': history.get(item_id, []), 'is_demo': True,
                             'persistence': 'process-memory'}) if item else None

    def change_expiry(self, item_id: str, change: ExpiryChange, actor_id: str):
        with self._lock:
            items, history, requests = self._state
            request_id = str(change.request_id)
            fingerprint = request_fingerprint(item_id, actor_id, change)
            if request_id in requests:
                previous_fingerprint, response = requests[request_id]
                if previous_fingerprint != fingerprint:
                    raise DemoChangeError(409, 'Bu işlem kimliği farklı bir istek için kullanılmış.')
                return deepcopy(response)
            updated, event = calculate_change(items.get(item_id), change, actor_id, list(items.values()))
            updated['id'] = item_id
            if hasattr(change, 'action'):
                event['subscriber_id'] = item_id
            events = [event, *history.get(item_id, [])]
            response = {'item': updated, 'history': events, 'is_demo': True, 'persistence': 'process-memory'}
            # Build and copy all results first. Publish record, audit and idempotency result together.
            result = deepcopy(response)
            next_state = ({**items, item_id: updated}, {**history, item_id: events},
                          {**requests, request_id: (fingerprint, deepcopy(response))})
            self._state = next_state
            return result


class ConfiguredDemoStore:
    """Lazy PostgreSQL adapter. Import/startup performs neither IO nor migration."""
    def __init__(self):
        self._adapter = None
        self._lock = RLock()

    def _get(self):
        with self._lock:
            if self._adapter is None:
                from app.core.database import engine
                from app.adapters.demo_subscriptions import PostgresDemoStore
                self._adapter = PostgresDemoStore(engine)
            return self._adapter

    def list_items(self):
        return self._get().list_items()

    def detail(self, item_id):
        return self._get().detail(item_id)

    def change_expiry(self, item_id, change, actor_id):
        return self._get().change_expiry(item_id, change, actor_id)

    def create_subscriber(self, command, actor_id):
        return self._get().create_subscriber(command, actor_id)

    def change_subscriber(self, item_id, command, actor_id):
        return self._get().change_subscriber(item_id, command, actor_id)

    def report_records(self, *args):
        return self._get().report_records(*args)

    def alarm_snapshot(self):
        from app.adapters.alarm_actions import snapshot
        return snapshot(self._get())

    def alarm_action(self, *args):
        from app.adapters.alarm_actions import mutate
        return mutate(self._get(), *args)

    def ping(self):
        return self._get().ping()


store = ConfiguredDemoStore()


def calculate_quick(item, change, actor_id, items=None):
    from app.services.demo_data import ROUTERS
    if not any(r['id'] == change.router_id and r['name'] == change.router_name and r['is_demo'] for r in ROUTERS):
        raise DemoChangeError(422, 'Sentetik router seçin.')
    today = datetime.now(ZoneInfo('Europe/Istanbul')).date()
    creating = change.action == 'CREATE'
    if creating:
        if item or change.expected_revision != 0 or change.expected_expires_on is not None:
            raise DemoChangeError(409, 'Oluşturma kimliği kullanılmış.')
        from app.schemas.subscriber_management import SubscriberCreate
        from app.services.demo_management import calculate_create
        from pydantic import ValidationError
        try:
            command = SubscriberCreate.model_validate(dict(
                request_id=str(change.request_id), confirmed=change.confirmed,
                username=change.username, customer_name=change.customer_name, plan=change.plan,
                source=change.expected_source, status=change.status, router_id=change.router_id,
                expires_on=change.expires_on.isoformat() if change.expires_on else None))
        except ValidationError:
            raise DemoChangeError(422, 'Geçerli demo abone alanlarını seçin.') from None
        created, event = calculate_create(command, actor_id, items or [])
        event.update(action='CREATE', router_name=created['router_name'], router_id=change.router_id,
                     previous_plan=None, plan=created['plan'], previous_status=None, status=created['status'],
                     previous_expires_on=None, expires_on=created['expires_on'])
        return created, event
    if not item:
        raise DemoChangeError(404, 'Kayıt bulunamadı')
    old = item.get('expires_on')
    if (item.get('is_demo') is not True or item.get('source') not in ('LOCAL', 'RADIUS')):
        raise DemoChangeError(403, 'Yalnız kaynağı bilinen sentetik demo kayıtları değiştirilebilir.')
    if (item['revision'] != change.expected_revision or item['source'] != change.expected_source
            or old != (change.expected_expires_on.isoformat() if change.expected_expires_on else None)
            or item['router_name'] != change.router_name
            or item.get('router_id') not in (None, change.router_id)):
        raise DemoChangeError(409, 'Kayıt değişmiş; yeniden yükleyip onaylayın.')
    new_date = change.expires_on
    if change.action == 'EXTEND' and change.days:
        if not old:
            raise DemoChangeError(422, 'Bitiş bilinmiyor; özel tarih seçin.')
        target = max(date.fromisoformat(old), today) + timedelta(days=change.days)
        if target != new_date:
            raise DemoChangeError(409, 'Uzatma önizlemesi değişmiş; tekrar onaylayın.')
    if (creating or change.action == 'EXTEND') and (new_date is None or new_date < today or (not creating and new_date.isoformat() == old)):
        raise DemoChangeError(422, 'Geçerli ve farklı bitiş tarihi seçin.')
    if change.action in ('PLAN', 'STATUS') and (new_date.isoformat() if new_date else None) != old:
        raise DemoChangeError(422, 'Bu işlem bitiş tarihini değiştiremez.')
    updated = {**item, 'revision': item['revision'] + 1}
    if creating or change.action == 'EXTEND':
        updated['expires_on'] = new_date.isoformat()
    if change.action in ('PLAN', 'STATUS'):
        from app.schemas.subscriber_management import SubscriberChange
        from app.services.demo_management import calculate_management_change
        field = 'plan' if change.action == 'PLAN' else 'status'
        command = SubscriberChange.model_validate(dict(request_id=str(change.request_id), confirmed=True,
            expected_revision=change.expected_revision, expected_source=change.expected_source,
            operation='PLAN_CHANGE' if field == 'plan' else 'STATUS_CHANGE', expected_value=item[field],
            value=change.plan.strip() if field == 'plan' else change.status))
        updated, event = calculate_management_change(item, command, actor_id)
        event.update(action=change.action, router_name=item['router_name'], router_id=change.router_id,
                     previous_plan=item['plan'], plan=updated['plan'], previous_status=item['status'],
                     status=updated['status'], previous_expires_on=old, expires_on=old)
        return updated, event
    event = dict(id=str(change.request_id), occurred_at=datetime.now(timezone.utc).isoformat(),
                 previous_expires_on=old, expires_on=updated['expires_on'], operation='RENEWAL' if change.days else 'DATE_EDIT',
                 source=item['source'], actor_id=actor_id, is_demo=True, action=change.action,
                 previous_plan=None if creating else item['plan'], plan=updated['plan'],
                 previous_status=None if creating else item['status'], status=updated['status'], router_name=item['router_name'], router_id=change.router_id)
    return updated, event
