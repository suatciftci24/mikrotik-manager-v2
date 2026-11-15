"""Read projection contract, no PostgreSQL or identity writes."""
import os
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock,patch
from app.services import identity

class AuditActorNames(TestCase):
    def test_batch_reads_only_requested_names_in_verified_identity_source(self):
        store=MagicMock(schema='v26_acceptance')
        connection=store.engine.connect.return_value.__enter__.return_value
        connection.execute.return_value.mappings.return_value=[{'id':'actor','username':'existing.operator'}]
        state=SimpleNamespace(users_ready=True,closed=True)
        with patch.dict(os.environ,{'V2_DEPLOYMENT_PROFILE':'v26-isolated-acceptance'}),patch.object(identity,'adapter',return_value=store),patch.object(identity,'inspect_setup',return_value=state):
            self.assertEqual(identity.audit_actor_usernames(['actor','actor']),{'actor':'existing.operator'})
        store._verify.assert_called_once_with(connection)
        statement,params=connection.execute.call_args.args
        self.assertEqual(params,{'ids':['actor']})
        sql=str(statement)
        self.assertIn('SELECT id,username',sql)
        self.assertIn("account_origin='LOCAL'",sql)
        self.assertIn("id<>'demo-user'",sql)
        for secret in ('password','email','permissions'):self.assertNotIn(secret,sql)

    def test_missing_unready_or_foreign_source_never_invents_identity(self):
        with patch.object(identity,'adapter') as adapter:
            self.assertEqual(identity.audit_actor_usernames([]),{})
            adapter.assert_not_called()
        for schema,ready,closed in [('v2_demo',True,True),('v26_acceptance',False,False),('v26_acceptance',True,False)]:
            store=MagicMock(schema=schema)
            with patch.dict(os.environ,{'V2_DEPLOYMENT_PROFILE':'v26-isolated-acceptance'}),patch.object(identity,'adapter',return_value=store),patch.object(identity,'inspect_setup',return_value=SimpleNamespace(users_ready=ready,closed=closed)):
                self.assertEqual(identity.audit_actor_usernames(['actor']),{})
                store.engine.connect.return_value.__enter__.return_value.execute.assert_not_called()
