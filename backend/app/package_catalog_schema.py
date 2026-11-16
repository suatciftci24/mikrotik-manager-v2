"""Inspect the existing package catalog; never create or alter database objects."""
from app.demo_repair import require
from app.models.package import Package, PackageEvent

TABLES = (Package.__table__, PackageEvent.__table__)


def validate(check, schema='v2_subscriber_workspace'):
    for table in TABLES:
        columns = {c['name']: c for c in check.get_columns(table.name, schema=schema)}
        require(set(columns) == set(table.columns.keys()), 'Paket sütunları farklı.')
        for column in table.columns:
            actual = columns[column.name]
            require(str(actual['type']).upper() == str(column.type).upper()
                    and actual['nullable'] == column.nullable, 'Paket sütun kuralları farklı.')
        require(check.get_pk_constraint(table.name, schema=schema)['constrained_columns'] == ['id'],
                'Paket primary key farklı.')
        indexes = {i['name']: i['column_names'] for i in check.get_indexes(table.name, schema=schema)}
        require(all(indexes.get(i.name) == [c.name for c in i.columns] for i in table.indexes),
                'Paket indeksi eksik.')
    require(any(u['column_names'] == ['name_key'] for u in check.get_unique_constraints('packages', schema=schema)),
            'Paket adı unique kuralı eksik.')
    rules = [''.join(c['sqltext'].split()).strip('()') for c in check.get_check_constraints('packages', schema=schema)]
    require('revision>=1' in rules, 'Paket revision kuralı eksik.')
