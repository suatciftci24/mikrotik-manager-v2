"""Read-only failure classification; no sockets, real DB, migrations or payload output."""
from unittest import TestCase
from unittest.mock import Mock,patch
from sqlalchemy.exc import ProgrammingError,OperationalError,SQLAlchemyError,IntegrityError
from fastapi import HTTPException
from app.services.router_workspace import boundary,storage_error_detail,WorkspaceError
from app.services.demo_subscriptions import DemoStorageUnavailable
from app.api.v1.router_workspace import execute

CANARY='PRIVATE_PASSWORD_PAYLOAD_CANARY'
def failure(state,statement='SELECT private_value FROM v2_router_workspace.records',kind=ProgrammingError):
    original=Exception(CANARY);original.sqlstate=state
    return kind(statement,{'secret':CANARY},original)

class WorkspaceStorageErrors(TestCase):
    def test_missing_relations_identify_only_their_own_migration(self):
        for table,migration in [('v2_router_workspace.records','007'),('v2_router_workspace.audit','007'),('v2_subscriber_workspace.subscribers','008'),('v2_subscriber_workspace.events','008')]:
            message=storage_error_detail(failure('42P01','SELECT * FROM '+table))
            self.assertIn('migration '+migration,message);self.assertIn('bulunamadı',message)
            self.assertNotIn(CANARY,message)
        message=storage_error_detail(failure('42P01','SELECT marker FROM v2_demo.schema_state'))
        self.assertNotIn('007',message);self.assertIn('numarası doğrulanmadı',message)

    def test_joined_workspaces_and_missing_schema_do_not_guess_the_missing_table(self):
        message=storage_error_detail(failure('42P01','SELECT * FROM v2_subscriber_workspace.subscribers LEFT JOIN v2_router_workspace.records ON false'))
        self.assertIn('007 ve 008',message);self.assertIn('eksik nesne',message)
        self.assertIn('008',storage_error_detail(failure('3F000','SELECT * FROM v2_subscriber_workspace.events')))

    def test_permissions_connection_auth_column_and_profile_are_not_missing_007(self):
        for error,reason in [(failure('42501'),'yetkisi yetersiz'),(failure('42703'),'şema/sürüm'),(failure('28P01',kind=OperationalError),'kimlik doğrulaması'),(failure('08006',kind=OperationalError),'bağlantısı'),(OperationalError(None,None,Exception(CANARY)),'bağlantısı'),(DemoStorageUnavailable(CANARY),'depo kimliği'),(SQLAlchemyError(CANARY),'teşhis gerekli')]:
            message=storage_error_detail(error)
            self.assertIn(reason,message);self.assertNotIn('007',message);self.assertNotIn(CANARY,message)

    def test_api_preserves_503_without_driver_sql_or_sensitive_payload(self):
        @boundary
        def read():raise failure('42501')
        with self.assertRaises(HTTPException) as result:execute(read)
        self.assertEqual(result.exception.status_code,503)
        self.assertIn('yetkisi yetersiz',result.exception.detail)
        self.assertNotIn(CANARY,result.exception.detail)
        self.assertNotIn('SELECT',result.exception.detail)

    def test_existing_domain_and_integrity_failures_keep_their_status(self):
        @boundary
        def domain():raise WorkspaceError(404,'Kayıt bulunamadı')
        with self.assertRaises(WorkspaceError) as result:domain()
        self.assertEqual(result.exception.status,404)
        @boundary
        def integrity():raise IntegrityError(None,None,Exception(CANARY))
        with self.assertRaises(WorkspaceError) as result:integrity()
        self.assertEqual(result.exception.status,409);self.assertNotIn(CANARY,result.exception.detail)

    def test_guard_marker_query_failure_does_not_turn_into_workspace_migration(self):
        from app.services.router_workspace import guard
        session=Mock();session.connection.return_value.execute.side_effect=failure('42P01','SELECT marker FROM v2_demo.schema_state')
        with patch('app.services.router_workspace.PostgresDemoStore') as adapter:
            adapter.return_value._verify.side_effect=session.connection.return_value.execute.side_effect
            with self.assertRaises(ProgrammingError) as error:guard(session)
        self.assertNotIn('007',storage_error_detail(error.exception))
