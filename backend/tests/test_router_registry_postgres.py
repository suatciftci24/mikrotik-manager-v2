"""Opt-in real PostgreSQL registry transactions with a mocked device, never real targets."""
import os
import tempfile
from pathlib import Path
from unittest import skipUnless
from unittest.mock import Mock, patch
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
import test_router_registry as cases
from app.core.database import engine
from app.demo_repair import preflight, verify_database
from app.local_router_registry import MIGRATION, validate_schema, demo_digest
from app.adapters.router_secrets import RouterSecretVault
from app.adapters.router_api_ssl import ConnectionPolicy
from app.services import router_registry as service
from sqlalchemy import inspect


@skipUnless(os.environ.get('V2_RUN_REGISTRY_PG_TESTS')=='1','Explicit local V2 PostgreSQL acceptance required')
class PostgresRegistryTransactions(cases.RegistryTests):
    def setUp(self):
        preflight(engine);verify_database(engine)
        with engine.connect() as connection:self.baseline=demo_digest(connection)
        self.schema='v2_registry_test_'+uuid4().hex
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.addCleanup(self.cleanup_schema)
        with engine.begin() as connection:
            connection.execute(text(f'SET LOCAL search_path TO "{self.schema}"'))
            connection.exec_driver_sql(MIGRATION.read_text())
            validate_schema(inspect(connection),self.schema)
        self.sessions=sessionmaker(bind=engine.execution_options(schema_translate_map={None:self.schema}),expire_on_commit=False)
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.vault=RouterSecretVault(Path(directory.name)/'registry'/'secrets')
        self.client=Mock();self.client.probe.return_value=dict(identity='SYNTHETIC-LAB',model='SYNTHETIC-MODEL',routeros_version='7.20.1')
        self.policy=ConnectionPolicy(True,'10.77.0.1',('10.77.0.0/24',))
        self.registry=service.RouterRegistry(self.sessions,self.vault,self.client,lambda:self.policy)
        tls=patch.object(service,'verified_tls_context',return_value=Mock());tls.start();self.addCleanup(tls.stop)

    def cleanup_schema(self):
        # Generated per-test schema only; public registry and demo records never deleted.
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
            self.assertEqual(demo_digest(connection),self.baseline)
