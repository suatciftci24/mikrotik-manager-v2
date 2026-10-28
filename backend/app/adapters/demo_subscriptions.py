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
    def report_records(self, start, until, cutoff, router_id, router_name, subscriber_id, operation, limit, offset, scope_routers=None):
        """Bounded audit response and aggregates in one read-only snapshot; no detail fan-out."""
        from app.services.demo_data import ROUTERS
        scope=ROUTERS if scope_routers is None else scope_routers
        ids=[r['id'] for r in scope]
        names=[r['name'] for r in scope if sum(x['name']==r['name'] for x in ROUTERS)==1]
        params=dict(start=start,until=until,cutoff=cutoff,router=router_id,name=router_name,
                    subscriber=subscriber_id,operation=operation,limit=limit,offset=offset,scope_ids=ids,scope_names=names)
        base=f"""FROM {self.schema}.events e JOIN {self.schema}.subscribers s ON s.id=e.subscriber_id
          WHERE (e.payload->>'occurred_at')::timestamptz >= :start
          AND (e.payload->>'occurred_at')::timestamptz < :until
          AND (e.payload->>'occurred_at')::timestamptz <= :cutoff
          AND (:router='' OR s.payload->>'router_id'=:router OR
               (s.payload->>'router_id' IS NULL AND s.payload->>'router_name'=:name))
          AND (:subscriber='' OR s.id=:subscriber)
          AND (s.payload->>'router_id'=ANY(CAST(:scope_ids AS text[])) OR
              (s.payload->>'router_id' IS NULL AND s.payload->>'router_name'=ANY(CAST(:scope_names AS text[]))))"""
        with self.engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with connection.begin():
                connection.execute(text('SET TRANSACTION READ ONLY'))
                self._verify(connection)
                items=list(connection.execute(text(f'SELECT payload FROM {self.schema}.subscribers')).scalars())
                groups=list(connection.execute(text("SELECT e.payload->>'operation' AS operation, e.payload->'new_values'->>'status' AS status, count(*) AS total "+base+" GROUP BY 1,2"),params).mappings())
                where=base+" AND (:operation='' OR e.payload->>'operation'=:operation)"
                total=connection.execute(text('SELECT count(*) '+where),params).scalar_one()
                rows=connection.execute(text("SELECT e.payload AS event,s.payload AS subscriber "+where+" ORDER BY (e.payload->>'occurred_at')::timestamptz DESC,e.id LIMIT :limit OFFSET :offset"),params).mappings()
                audits=[{**row['event'],'subscriber_id':row['subscriber']['id'],
                         **{key:row['subscriber'].get(key) for key in ('customer_name','username','router_id','router_name','access_type')}} for row in rows]
        return items,audits,total,[dict(row) for row in groups]

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
                connection.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:id,0))'), {'id': item_id})
                if getattr(change, 'action', None) == 'CREATE':
                    connection.execute(text(f'LOCK TABLE {self.schema}.subscribers IN SHARE ROW EXCLUSIVE MODE'))
                item = self._item(connection, item_id, lock=True)
                cached = self._request(connection, request_id, fingerprint)
                if cached is not None:
                    return deepcopy(cached)
                items = list(connection.execute(text(f'SELECT payload FROM {self.schema}.subscribers')).scalars()) if getattr(change, 'action', None) == 'CREATE' else None
                updated, event = calculate_change(item, change, actor_id, items)
                updated['id'] = item_id
                if hasattr(change, 'action'):
                    event['subscriber_id'] = item_id
                response = self._persist(connection, updated, event, fingerprint, create=item is None)
                # No success is returned until context-manager COMMIT completes.
            return response
        except IntegrityError:
            # Another subscriber may race on the globally unique request UUID.
            with self.engine.connect() as connection:
                cached = self._request(connection, request_id, fingerprint)
                if cached is not None:
                    return deepcopy(cached)
            raise DemoStorageUnavailable() from None


    def _persist(self, connection, item, event, fingerprint, create=False):
        item_id, request_id = item['id'], event['id']
        if create:
            connection.execute(text(f'INSERT INTO {self.schema}.subscribers(id,payload,revision) VALUES (:id,CAST(:payload AS jsonb),:revision)'),
                               {'id': item_id, 'payload': json.dumps(item), 'revision': item['revision']})
        else:
            connection.execute(text(f'UPDATE {self.schema}.subscribers SET payload=CAST(:payload AS jsonb), revision=:revision WHERE id=:id'),
                               {'id': item_id, 'payload': json.dumps(item), 'revision': item['revision']})
        connection.execute(text(f'INSERT INTO {self.schema}.events(id,subscriber_id,revision,payload) VALUES (:id,:subscriber,:revision,CAST(:payload AS jsonb))'),
                           {'id': request_id, 'subscriber': item_id, 'revision': item['revision'], 'payload': json.dumps(event)})
        response = self._response(item, self._history(connection, item_id))
        connection.execute(text(f'INSERT INTO {self.schema}.requests(id,subscriber_id,fingerprint,response) VALUES (:id,:subscriber,:fingerprint,CAST(:response AS jsonb))'),
                           {'id': request_id, 'subscriber': item_id, 'fingerprint': fingerprint, 'response': json.dumps(response)})
        return response

    @storage_errors
    def create_subscriber(self, command, actor_id):
        from app.services.demo_management import calculate_create
        fingerprint = request_fingerprint('create-subscriber', actor_id, command)
        # Creation alone serializes the username check and insert across API workers.
        # No username/source/router edits exist; expiry and status/plan keep identity intact.
        with self.engine.begin() as connection:
            self._verify(connection)
            connection.execute(text(f'LOCK TABLE {self.schema}.subscribers IN SHARE ROW EXCLUSIVE MODE'))
            cached = self._request(connection, str(command.request_id), fingerprint)
            if cached is not None:
                return deepcopy(cached)
            items = list(connection.execute(text(f'SELECT payload FROM {self.schema}.subscribers')).scalars())
            item, event = calculate_create(command, actor_id, items)
            response = self._persist(connection, item, event, fingerprint, create=True)
        return response

    @storage_errors
    def change_subscriber(self, item_id, command, actor_id):
        from app.services.demo_management import calculate_management_change
        fingerprint = request_fingerprint(item_id, actor_id, command)
        try:
            with self.engine.begin() as connection:
                self._verify(connection)
                item = self._item(connection, item_id, lock=True)
                cached = self._request(connection, str(command.request_id), fingerprint)
                if cached is not None:
                    return deepcopy(cached)
                updated, event = calculate_management_change(item, command, actor_id)
                response = self._persist(connection, updated, event, fingerprint)
            return response
        except IntegrityError:
            with self.engine.connect() as connection:
                cached = self._request(connection, str(command.request_id), fingerprint)
                if cached is not None:
                    return deepcopy(cached)
            raise DemoStorageUnavailable() from None
