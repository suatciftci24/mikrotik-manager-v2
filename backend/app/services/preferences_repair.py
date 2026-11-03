"""Explicit maintenance only. Caller owns target gates, backup and transaction.

No engine creation, migration, startup hook, HTTP route or implicit commit.
This module can be streamed into the existing Fresh Pilot interpreter without
installing or importing a changed application build.
"""
import hashlib
import json
import re
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from app.services.system_settings import Values


class RepairBlocked(Exception):
    """Only fixed codes cross the maintenance logging boundary."""


def require(ok, code):
    if not ok:
        raise RepairBlocked(code)


def lock(c):
    # Same advisory lock as normal settings saves. Table locks also cover writers
    # unaware of the application advisory lock; timeouts are set by the caller.
    c.execute(text("SELECT pg_advisory_xact_lock(hashtext('v2-settings'))"))
    c.execute(text('LOCK TABLE v2_demo.settings_records, v2_demo.settings_audit IN SHARE ROW EXCLUSIVE MODE'))


def inspect_default(c):
    row = c.execute(text("SELECT * FROM v2_demo.settings_records WHERE id='default'")).mappings().one_or_none()
    if row is None:
        return None
    try:
        Values.model_validate(row['payload'])
        require(type(row['revision']) is int and row['revision'] >= 0, 'DEFAULT_SETTINGS_INVALID')
        require(isinstance(row['updated_at'], datetime) and row['updated_at'].tzinfo is not None, 'DEFAULT_SETTINGS_INVALID')
    except (ValueError, KeyError, TypeError):
        raise RepairBlocked('DEFAULT_SETTINGS_INVALID') from None
    return dict(row)


def admin(c, actor_id):
    # Recheck active LOCAL ADMIN and permanent seal in this write transaction.
    from app.services.identity import public_user
    row = c.execute(text('''SELECT u.* FROM v2_demo.users u
        JOIN v2_demo.first_admin_setup s ON s.admin_id=u.id AND s.singleton=1
        WHERE u.id=:actor FOR SHARE OF u,s'''), {'actor': actor_id}).mappings().one_or_none()
    require(row is not None and row['active'] is True and row['role'] == 'ADMIN'
            and row['account_origin'] == 'LOCAL', 'LOCAL_ADMIN_REQUIRED')
    require(public_user(dict(row), bootstrap_closed=True)['can_manage_users'] is True, 'LOCAL_ADMIN_REQUIRED')
    state = c.execute(text('SELECT first_admin_initialized AND identity_initialized FROM v2_demo.schema_state WHERE version=1')).scalar_one()
    require(state is True, 'ADMIN_SEAL_REQUIRED')


def audit(c, request_id, actor_id, operation, previous, new, response, backup_sha256):
    fingerprint = json.dumps([operation, actor_id, str(request_id), backup_sha256], sort_keys=True)
    c.execute(text('''INSERT INTO v2_demo.settings_audit
        (id,record_id,actor_id,previous_values,new_values,result,fingerprint,response)
        VALUES (:id,'default',:actor,CAST(:previous AS jsonb),CAST(:new AS jsonb),
                'SUCCESS',:fingerprint,CAST(:response AS jsonb))'''),
        {'id': str(request_id), 'actor': actor_id,
         'previous': json.dumps(previous), 'new': json.dumps(new),
         'fingerprint': fingerprint, 'response': json.dumps(response)})


def repair(c, actor_id, request_id, backup_sha256):
    request_id = UUID(str(request_id))
    require(bool(re.fullmatch('[a-f0-9]{64}', backup_sha256)), 'VERIFIED_BACKUP_REQUIRED')
    lock(c)
    admin(c, actor_id)
    old = inspect_default(c)
    if old is not None:
        return {'status': 'NOOP_EXISTING_VALID', 'changed': False}
    used = c.execute(text('SELECT 1 FROM v2_demo.settings_audit WHERE id=:id'), {'id': str(request_id)}).scalar_one_or_none()
    require(used is None, 'REPAIR_REQUEST_ALREADY_USED')
    payload = Values().model_dump()
    inserted = c.execute(text('''INSERT INTO v2_demo.settings_records(id,payload)
        VALUES ('default',CAST(:payload AS jsonb)) ON CONFLICT(id) DO NOTHING
        RETURNING id'''), {'payload': json.dumps(payload)}).scalar_one_or_none()
    # Unique key is the final guard even for a writer that did not take our lock.
    row = inspect_default(c)
    require(row is not None, 'DEFAULT_SETTINGS_MISSING_AFTER_INSERT')
    if inserted is None:
        return {'status': 'NOOP_EXISTING_VALID', 'changed': False}
    response = {'status': 'CREATED', 'operation': 'DEFAULT_SETTINGS_REPAIR', 'changed': True,
                'repair_id': str(request_id), 'revision': row['revision'],
                'updated_at': row['updated_at'].isoformat(),
                'payload_sha256': hashlib.sha256(json.dumps(row['payload'], sort_keys=True).encode()).hexdigest(),
                'backup_sha256': backup_sha256}
    audit(c, request_id, actor_id, response['operation'], None, payload, response, backup_sha256)
    return response


def rollback(c, actor_id, repair_id, rollback_id):
    """Restore only the absent pre-image; refuse any intervening preference edit."""
    repair_id, rollback_id = UUID(str(repair_id)), UUID(str(rollback_id))
    require(repair_id != rollback_id, 'ROLLBACK_ID_REUSED')
    lock(c)
    admin(c, actor_id)
    receipt = c.execute(text("SELECT * FROM v2_demo.settings_audit WHERE id=:id AND record_id='default'"),
                        {'id': str(repair_id)}).mappings().one_or_none()
    require(receipt is not None and receipt['result'] == 'SUCCESS', 'REPAIR_RECEIPT_REQUIRED')
    response = receipt['response']
    require(response.get('operation') == 'DEFAULT_SETTINGS_REPAIR' and response.get('changed') is True
            and response.get('repair_id') == str(repair_id) and receipt['previous_values'] is None,
            'REPAIR_RECEIPT_INVALID')
    used = c.execute(text('SELECT response FROM v2_demo.settings_audit WHERE id=:id'),
                     {'id': str(rollback_id)}).scalar_one_or_none()
    row = inspect_default(c)
    if used is not None:
        require(used.get('operation') == 'DEFAULT_SETTINGS_REPAIR_ROLLBACK'
                and used.get('repair_id') == str(repair_id) and row is None, 'ROLLBACK_ID_REUSED')
        return {'status': 'NOOP_ALREADY_ROLLED_BACK', 'changed': False}
    require(row is not None and row['revision'] == response['revision']
            and row['updated_at'].isoformat() == response['updated_at']
            and row['payload'] == receipt['new_values'], 'DEFAULT_CHANGED_ROLLBACK_REFUSED')
    digest = hashlib.sha256(json.dumps(row['payload'], sort_keys=True).encode()).hexdigest()
    require(digest == response['payload_sha256'], 'REPAIR_RECEIPT_INVALID')
    deleted = c.execute(text("DELETE FROM v2_demo.settings_records WHERE id='default' AND revision=:revision AND updated_at=:updated RETURNING id"),
                        {'revision': row['revision'], 'updated': row['updated_at']}).scalar_one_or_none()
    require(deleted == 'default', 'DEFAULT_CHANGED_ROLLBACK_REFUSED')
    result = {'status': 'ROLLED_BACK', 'operation': 'DEFAULT_SETTINGS_REPAIR_ROLLBACK',
              'repair_id': str(repair_id), 'changed': True}
    audit(c, rollback_id, actor_id, result['operation'], row['payload'], {'state': 'ABSENT'}, result, response['backup_sha256'])
    return result
