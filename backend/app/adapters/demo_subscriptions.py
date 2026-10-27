"""PostgreSQL adapter restricted to the configured, isolated V2 development DB."""
from copy import deepcopy
from functools import wraps
import json
import re
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.services.demo_subscriptions import DemoChangeError, DemoStorageUnavailable, calculate_change, request_fingerprint


def storage_errors(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except SQLAlchemyError:
            raise DemoStorageUnavailable() from None
    return guarded


class PostgresDemoStore:
    persistence = 'local-postgresql-demo'

    def __init__(self, engine, schema='v2_demo'):
        url = engine.url
        if (url.drivername != 'postgresql+psycopg' or url.host not in ('127.0.0.1', 'localhost', '::1')
                or url.port != 55432 or url.database != 'mikrotik_manager_v2' or url.username != 'v2_local'):
            raise DemoStorageUnavailable()
        if schema != 'v2_demo' and not re.fullmatch(r'v2_demo_test_[a-f0-9]{32}', schema):
            raise ValueError('Invalid isolated demo schema')
        self.engine, self.schema = engine, schema

    def _verify(self, connection):
        marker = connection.execute(text(f'SELECT marker FROM {self.schema}.schema_state WHERE version=1')).scalar_one()
        if marker != 'mikrotik-manager-v2-synthetic-only':
            raise DemoStorageUnavailable()

    def _item(self, connection, item_id, lock=False):
        suffix = ' FOR UPDATE' if lock else ''
        row = connection.execute(text(f'SELECT payload, revision FROM {self.schema}.subscribers WHERE id=:id{suffix}'), {'id': item_id}).mappings().one_or_none()
        return {**row['payload'], 'revision': row['revision']} if row else None

    def _history(self, connection, item_id):
        return list(connection.execute(text(f'SELECT payload FROM {self.schema}.events WHERE subscriber_id=:id ORDER BY revision DESC'), {'id': item_id}).scalars())

    def _response(self, item, history):
        return {'item': item, 'history': history, 'is_demo': True, 'persistence': self.persistence}

    def _request(self, connection, request_id, fingerprint):
        cached = connection.execute(text(f'SELECT fingerprint, response FROM {self.schema}.requests WHERE id=:id'), {'id': request_id}).mappings().one_or_none()
        if cached:
            if cached['fingerprint'] != fingerprint:
                raise DemoChangeError(409, 'Bu işlem kimliği farklı bir istek için kullanılmış.')
            return cached['response']
        return None

    @storage_errors
    def ping(self):
        with self.engine.connect() as connection:
            self._verify(connection)
            return True

    @storage_errors
    def list_items(self):
        with self.engine.connect() as connection:
            self._verify(connection)
            return [{**row.payload, 'revision': row.revision} for row in connection.execute(text(f'SELECT payload, revision FROM {self.schema}.subscribers ORDER BY id'))]

    @storage_errors
    def detail(self, item_id):
        # Repeatable read keeps the item and its history on the same snapshot.
        with self.engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with connection.begin():
                self._verify(connection)
                item = self._item(connection, item_id)
                return self._response(item, self._history(connection, item_id)) if item else None

    @storage_errors
    def change_expiry(self, item_id, change, actor_id):
        fingerprint = request_fingerprint(item_id, actor_id, change)
        request_id = str(change.request_id)
        try:
            with self.engine.begin() as connection:
                self._verify(connection)
                item = self._item(connection, item_id, lock=True)
                cached = self._request(connection, request_id, fingerprint)
                if cached is not None:
                    return deepcopy(cached)
                updated, event = calculate_change(item, change, actor_id)
                connection.execute(text(f'UPDATE {self.schema}.subscribers SET payload=CAST(:payload AS jsonb), revision=:revision WHERE id=:id'),
                                   {'id': item_id, 'payload': json.dumps(updated), 'revision': updated['revision']})
                connection.execute(text(f'INSERT INTO {self.schema}.events(id, subscriber_id, revision, payload) VALUES (:id,:subscriber,:revision,CAST(:payload AS jsonb))'),
                                   {'id': request_id, 'subscriber': item_id, 'revision': updated['revision'], 'payload': json.dumps(event)})
                response = self._response(updated, self._history(connection, item_id))
                connection.execute(text(f'INSERT INTO {self.schema}.requests(id,subscriber_id,fingerprint,response) VALUES (:id,:subscriber,:fingerprint,CAST(:response AS jsonb))'),
                                   {'id': request_id, 'subscriber': item_id, 'fingerprint': fingerprint, 'response': json.dumps(response)})
                # No success is returned until context-manager COMMIT completes.
            return response
        except IntegrityError:
            # Another subscriber may race on the globally unique request UUID.
            with self.engine.connect() as connection:
                cached = self._request(connection, request_id, fingerprint)
                if cached is not None:
                    return deepcopy(cached)
            raise DemoStorageUnavailable() from None
