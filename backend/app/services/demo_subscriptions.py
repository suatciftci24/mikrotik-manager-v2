"""Process-memory demo only. No database, filesystem, RouterOS or RADIUS writes."""
from copy import deepcopy
from datetime import date, datetime, timezone
from threading import RLock
from zoneinfo import ZoneInfo

from app.schemas.subscriber_events import ExpiryChange
from app.services.demo_data import SUBSCRIBERS


class DemoChangeError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


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
            fingerprint = (item_id, actor_id, change.model_dump_json())
            if request_id in requests:
                previous_fingerprint, response = requests[request_id]
                if previous_fingerprint != fingerprint:
                    raise DemoChangeError(409, 'Bu işlem kimliği farklı bir istek için kullanılmış.')
                return deepcopy(response)
            item = items.get(item_id)
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
            events = [event, *history.get(item_id, [])]
            response = {'item': updated, 'history': events, 'is_demo': True, 'persistence': 'process-memory'}
            # Build and copy all results first. Publish record, audit and idempotency result together.
            result = deepcopy(response)
            next_state = ({**items, item_id: updated}, {**history, item_id: events},
                          {**requests, request_id: (fingerprint, deepcopy(response))})
            self._state = next_state
            return result


store = DemoSubscriptionStore(SUBSCRIBERS)
