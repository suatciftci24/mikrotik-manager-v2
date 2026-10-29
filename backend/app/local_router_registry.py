"""Explicit migration 006 for the repo-owned local V2 PostgreSQL only. No device IO."""
import argparse
import re
from pathlib import Path
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from app.demo_repair import ROOT, RepairBlocked, preflight, require, verify_database
from app.models.router_registry import RegisteredRouter, RouterVerification, RouterRegistryAudit

TABLES=(RegisteredRouter.__table__,RouterVerification.__table__,RouterRegistryAudit.__table__)
MIGRATION=ROOT/'migrations/versions/006_router_registry.sql'


def validate_schema(inspector,schema='public'):
    for table in TABLES:
        columns={c['name']:c for c in inspector.get_columns(table.name,schema=schema)}
        require(set(columns)==set(table.columns.keys()),'Registry şeması eksik/farklı; otomatik onarım yapılmadı.')
        for column in table.columns:
            actual=columns[column.name]
            require(str(actual['type']).upper()==str(column.type).upper() and actual['nullable']==column.nullable,
                    'Registry sütun tipi/null kuralı farklı; mevcut tablo değiştirilmedi.')
        require(inspector.get_pk_constraint(table.name,schema=schema)['constrained_columns']==['id'],
                'Registry primary key farklı; duruldu.')
        indexes={i['name']:i['column_names'] for i in inspector.get_indexes(table.name,schema=schema)}
        require(all(indexes.get(index.name)==[c.name for c in index.columns] for index in table.indexes),
                'Registry indeksleri eksik/farklı; duruldu.')
    unique=inspector.get_unique_constraints(RegisteredRouter.__tablename__,schema=schema)
    require(any(u['column_names']==['management_address','port'] for u in unique),'Registry uç nokta unique kuralı eksik.')
    checks=inspector.get_check_constraints(RegisteredRouter.__tablename__,schema=schema)
    normalize=lambda value:re.sub(r'[\s()]','',value).lower()
    require(any(normalize(c['sqltext'])=='port>=1024andport<=65535andport<>8728' for c in checks),
            'Registry güvenli port CHECK kuralı eksik/farklı.')


def demo_digest(connection):
    # Only synthetic V2 business data; compare without printing any row values.
    return tuple(connection.execute(text(
        f"SELECT count(*), md5(COALESCE(string_agg(row_to_json(t)::text, '' ORDER BY row_to_json(t)::text),'')) FROM v2_demo.{name} t"
    )).one() for name in ('subscribers','events','requests'))


def prepare(destination):
    preflight(destination)
    verify_database(destination)  # Read-only marker/data_directory/privileges before DDL.
    with destination.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(62006006)'))
        require(connection.execute(text('SELECT current_database(),current_user,inet_server_port()')).one()==
                ('mikrotik_manager_v2','v2_local',55432),'V2 sunucu kimliği doğrulanamadı.')
        require(Path(connection.execute(text('SHOW data_directory')).scalar_one()).resolve()==
                (ROOT/'.local/postgres-v2-demo').resolve(),'V2 küme sahibi doğrulanamadı.')
        before=demo_digest(connection)
        found=set(inspect(connection).get_table_names(schema='public')) & {t.name for t in TABLES}
        require(not found or len(found)==len(TABLES),'Kısmi registry şeması var; veri değiştirilmedi.')
        if not found:
            connection.execute(text('SET LOCAL search_path TO public'))
            connection.exec_driver_sql(MIGRATION.read_text())
        validate_schema(inspect(connection))
        require(demo_digest(connection)==before,'Demo veri baseline değişti; migration geri alındı.')
    return 'already-current' if found else 'applied'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',required=True,help='Açık yerel V2 migration 006 hazırlığı')
    parser.parse_args(argv)
    from app.core.database import engine
    try:
        state=prepare(engine)
        print(f'PASS: local V2 migration 006 {state}; demo records unchanged. Device access not used.')
        return 0
    except (RepairBlocked,SQLAlchemyError,OSError) as error:
        detail=str(error) if isinstance(error,RepairBlocked) else type(error).__name__
        print('BLOCKED: '+detail+'; DB/credential ayrıntıları yazdırılmadı.')
        return 1
    finally:engine.dispose()


if __name__=='__main__':raise SystemExit(main())
