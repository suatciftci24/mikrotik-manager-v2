"""Alarm receipts share the existing V2 adapter/engine and synthetic marker boundary."""
import json
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import text
from app.adapters.demo_subscriptions import storage_errors
from app.services.demo_subscriptions import DemoChangeError
from app.services.alarms import project_alarms
from app.services.demo_data import ROUTERS


def ready(connection,schema):
    return all(connection.execute(text('SELECT to_regclass(:table)'),{'table':schema+'.'+name}).scalar_one() for name in ('alarm_actions','alarm_requests'))


def action_dict(row):
    return {**dict(row),'id':str(row['id']),'occurred_at':row['occurred_at'].isoformat()}


@storage_errors
def snapshot(adapter):
    with adapter.engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'));adapter._verify(connection)
            items=list(connection.execute(text(f'SELECT payload FROM {adapter.schema}.subscribers')).scalars())
            available=ready(connection,adapter.schema)
            actions=[action_dict(row) for row in connection.execute(text(f'SELECT * FROM {adapter.schema}.alarm_actions ORDER BY occurred_at,id')).mappings()] if available else []
    return items,actions,available


@storage_errors
def mutate(adapter,alarm_id,request_id,occurrence_id,action,actor_id):
    fingerprint=json.dumps([alarm_id,occurrence_id,action,actor_id],separators=(',',':'))
    with adapter.engine.begin() as connection:
        adapter._verify(connection)
        if not ready(connection,adapter.schema):raise DemoChangeError(503,'Alarm işlem şeması hazır değil; açık yerel alarms-init bakımını çalıştırın. Kayıt değiştirilmedi.')
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('v2-alarm-actions'))"))
        previous=connection.execute(text(f'SELECT fingerprint,response FROM {adapter.schema}.alarm_requests WHERE id=:id'),{'id':request_id}).mappings().one_or_none()
        if previous:
            if previous['fingerprint']!=fingerprint:raise DemoChangeError(409,'İstek kimliği farklı alarm işlemi için kullanılmış.')
            return previous['response']
        # Serialize against source writes so a stale occurrence cannot be acknowledged.
        connection.execute(text(f'LOCK TABLE {adapter.schema}.subscribers IN SHARE MODE'))
        items=list(connection.execute(text(f'SELECT payload FROM {adapter.schema}.subscribers')).scalars())
        alarms,_=project_alarms(items,ROUTERS,[],actor_id)
        alarm=next((row for row in alarms if row['id']==alarm_id),None)
        if alarm is None and action=='READ':
            archived=connection.execute(text(f'SELECT source_snapshot FROM {adapter.schema}.alarm_actions WHERE alarm_id=:alarm AND occurrence_id=:occurrence ORDER BY occurred_at DESC LIMIT 1'),dict(alarm=alarm_id,occurrence=occurrence_id)).scalar_one_or_none()
            if archived:alarm={**archived,'source_available':False}
        if not alarm:raise DemoChangeError(404,'Kaynak alarm bulunamadı.')
        if alarm['occurrence_id']!=occurrence_id:raise DemoChangeError(409,'Alarmın kaynak olayı değişmiş; yeniden yükleyin.')
        if action=='ACK' and alarm['source_state']=='RESOLVED':raise DemoChangeError(409,'Kaynakta çözülmüş alarm onaylanamaz.')
        params=dict(id=request_id,alarm=alarm_id,occurrence=occurrence_id,action=action,actor=actor_id,owner='' if action=='ACK' else actor_id,snapshot=json.dumps({k:v for k,v in alarm.items() if k not in ('action_history','acknowledgement','notification_read')}))
        row=connection.execute(text(f'''INSERT INTO {adapter.schema}.alarm_actions(id,alarm_id,occurrence_id,action,actor_id,owner,source_snapshot)
          VALUES (:id,:alarm,:occurrence,:action,:actor,:owner,CAST(:snapshot AS jsonb)) ON CONFLICT (alarm_id,occurrence_id,action,owner) DO NOTHING RETURNING *'''),params).mappings().one_or_none()
        if row is None:
            row=connection.execute(text(f'SELECT * FROM {adapter.schema}.alarm_actions WHERE alarm_id=:alarm AND occurrence_id=:occurrence AND action=:action AND owner=:owner'),params).mappings().one()
        response=dict(action={key:value for key,value in action_dict(row).items() if key!='source_snapshot'},is_demo=True)
        connection.execute(text(f'INSERT INTO {adapter.schema}.alarm_requests(id,fingerprint,response) VALUES (:id,:fingerprint,CAST(:response AS jsonb))'),dict(id=request_id,fingerprint=fingerprint,response=json.dumps(response)))
        return response


def initialize(adapter):
    from app.demo_repair import preflight, ROOT, require
    require(adapter.schema=='v2_demo','Alarm bakımı yalnız standart izole V2 demo şeması içindir.')
    preflight(adapter.engine)
    with adapter.engine.begin() as connection:
        adapter._verify(connection)
        directory=connection.execute(text('SHOW data_directory')).scalar_one()
        require(Path(directory).resolve()==(ROOT/'.local/postgres-v2-demo').resolve(),'Bu repo V2 kümesi doğrulanamadı; alarm şeması hazırlanmadı.')
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('v2-alarm-actions'))"))
        migration=ROOT/'migrations/versions/003_demo_alarm_actions.sql'
        for statement in migration.read_text().split(';'):
            if statement.strip():connection.execute(text(statement))
