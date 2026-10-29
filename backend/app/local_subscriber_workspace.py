"""Explicit 008 setup on the owned local V2 cluster; never at application startup."""
from sqlalchemy import inspect,text
from app.demo_repair import preflight,verify_database,require,RepairBlocked,ROOT
from app.local_router_registry import demo_digest
from app.local_router_workspace import validate as validate_routers
from app.models.subscriber_workspace import SyntheticSubscriber,SyntheticSubscriberEvent
TABLES=(SyntheticSubscriber.__table__,SyntheticSubscriberEvent.__table__)
SCHEMA='v2_subscriber_workspace'
MIGRATION=ROOT/'migrations/versions/008_subscriber_workspace.sql'

def validate(check,schema=SCHEMA,router_schema='v2_router_workspace'):
    require(set(check.get_table_names(schema=schema))=={'subscribers','events'},'Abone çalışma alanı şeması eksik/farklı.')
    for table in TABLES:
        actual={c['name']:c for c in check.get_columns(table.name,schema=schema)}
        require(set(actual)==set(table.columns.keys()),'Abone sütunları farklı.')
        for c in table.columns:require(str(actual[c.name]['type']).upper()==str(c.type).upper() and actual[c.name]['nullable']==c.nullable,'Abone sütun tipi/null kuralı farklı.')
        require(check.get_pk_constraint(table.name,schema=schema)['constrained_columns']==['id'],'Abone PK farklı.')
        indexes={i['name']:i['column_names'] for i in check.get_indexes(table.name,schema=schema)}
        require(all(indexes.get(i.name)==[c.name for c in i.columns] for i in table.indexes),'Abone indeksi eksik.')
    require(any(u['column_names']==['username_key'] for u in check.get_unique_constraints('subscribers',schema=schema)),'Kullanıcı adı unique kuralı eksik.')
    require(any(f['constrained_columns']==['router_id'] and f['referred_schema']==router_schema and f['referred_table']=='records' and f['referred_columns']==['id'] and f.get('options',{}).get('ondelete')=='RESTRICT' for f in check.get_foreign_keys('subscribers',schema=schema)),'Güvenli router ID foreign key eksik.')
    rules=' '.join(c['sqltext'] for c in check.get_check_constraints('subscribers',schema=schema))
    require(all(value in rules for value in ('PPPOE','HOTSPOT','LOCAL','RADIUS')),'Erişim türü/kaynak kuralı eksik.')

def prepare(destination):
    preflight(destination);verify_database(destination)
    with destination.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(62006008)'))
        validate_routers(inspect(connection));before=demo_digest(connection)
        existing=SCHEMA in inspect(connection).get_schema_names()
        if not existing:connection.exec_driver_sql(MIGRATION.read_text())
        validate(inspect(connection));require(demo_digest(connection)==before,'Eski demo verisi değişti; migration geri alındı.')
    return 'already-current' if existing else 'applied'

def main():
    import argparse
    from sqlalchemy.exc import SQLAlchemyError
    from app.core.database import engine
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true',required=True);parser.parse_args()
    try:print('PASS: isolated local subscriber migration 008 '+prepare(engine));return 0
    except (RepairBlocked,SQLAlchemyError,OSError) as e:print('BLOCKED: '+(str(e) if isinstance(e,RepairBlocked) else type(e).__name__));return 1
    finally:engine.dispose()
if __name__=='__main__':raise SystemExit(main())
