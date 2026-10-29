"""Explicit schema 007 setup in the repo-owned V2 database only."""
from sqlalchemy import inspect,text
from app.demo_repair import preflight,verify_database,require,RepairBlocked,ROOT
from app.local_router_registry import demo_digest
from app.models.router_workspace import RouterWorkspaceRecord,RouterWorkspaceAudit

TABLES=(RouterWorkspaceRecord.__table__,RouterWorkspaceAudit.__table__)
SCHEMA='v2_router_workspace'
MIGRATION=ROOT/'migrations/versions/007_router_workspace.sql'

def validate(inspector,schema=SCHEMA):
    require(set(inspector.get_table_names(schema=schema))=={'records','audit'},'Çalışma alanı şeması eksik/farklı; mevcut veri değiştirilmedi.')
    for table in TABLES:
        columns={c['name']:c for c in inspector.get_columns(table.name,schema=schema)}
        require(set(columns)==set(table.columns.keys()),'Çalışma alanı sütunları farklı.')
        for c in table.columns:
            require(str(columns[c.name]['type']).upper()==str(c.type).upper() and columns[c.name]['nullable']==c.nullable,'Çalışma alanı sütun kuralları farklı.')
        require(inspector.get_pk_constraint(table.name,schema=schema)['constrained_columns']==['id'],'Çalışma alanı primary key farklı.')
        indexes={i['name']:i['column_names'] for i in inspector.get_indexes(table.name,schema=schema)}
        require(all(indexes.get(i.name)==[c.name for c in i.columns] for i in table.indexes),'Çalışma alanı indeksleri eksik.')
    checks=inspector.get_check_constraints('records',schema=schema)
    require(any('DEMO_ROUTER' in c['sqltext'] and 'TRUST_PROFILE' in c['sqltext'] for c in checks),'Çalışma alanı tür kuralı eksik.')

def prepare(destination):
    preflight(destination);verify_database(destination)
    with destination.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(62006007)'))
        before=demo_digest(connection)
        existing=SCHEMA in inspect(connection).get_schema_names()
        if not existing:connection.exec_driver_sql(MIGRATION.read_text())
        validate(inspect(connection))
        require(demo_digest(connection)==before,'Demo verisi değişti; çalışma alanı migration geri alındı.')
    return 'already-current' if existing else 'applied'

def main():
    import argparse
    from sqlalchemy.exc import SQLAlchemyError
    from app.core.database import engine
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true',required=True);parser.parse_args()
    try:
        print('PASS: local V2 workspace migration 007 '+prepare(engine)+'; no device access.')
        return 0
    except (RepairBlocked,SQLAlchemyError,OSError) as error:
        print('BLOCKED: '+(str(error) if isinstance(error,RepairBlocked) else type(error).__name__))
        return 1
    finally:engine.dispose()

if __name__=='__main__':raise SystemExit(main())
