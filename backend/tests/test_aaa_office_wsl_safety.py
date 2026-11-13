"""Office guard tests only; never provision/connect/run real PostgreSQL."""
from unittest import TestCase
from unittest.mock import patch
from backend.tests import run_aaa_postgres_office_wsl as office
from backend.tests import run_aaa_postgres_wsl as provision


class OfficeAaaSafetyTests(TestCase):
    def test_foreign_host_denied_before_provision(self):
        with patch.object(office.platform,'node',return_value='foreign'),patch.object(provision,'prepare') as prepare:
            with self.assertRaisesRegex(RuntimeError,'OFFICE_WSL_IDENTITY_REJECTED'):office.main()
            prepare.assert_not_called()

    def test_invalid_cluster_id_cannot_reach_bridge(self):
        for value in (None,'foreign','',1):
            with self.assertRaisesRegex(RuntimeError,'VERIFIED_CLUSTER_ID_REQUIRED'):office.run_bridge(value)

    def test_office_guard_requires_actual_venv_and_clean_main_branch(self):
        # Foreign repo cannot become allowed via environment-only host selection.
        with patch.object(office.Path,'cwd',return_value=office.REPO.parent),patch.object(provision,'prepare') as prepare:
            with self.assertRaisesRegex(RuntimeError,'OFFICE_WSL_IDENTITY_REJECTED'):office.main()
            prepare.assert_not_called()

    def test_existing_root_still_refuses_before_socket_or_files(self):
        with patch.object(office,'office_guard'),patch.object(provision.os.path,'lexists',return_value=True), \
                patch.object(provision.socket,'socket') as socket,patch.object(provision,'OwnedRoot') as root:
            with self.assertRaisesRegex(RuntimeError,'ACCEPTANCE_ROOT_ALREADY_EXISTS'):office.main()
            socket.assert_not_called();root.assert_not_called()

    def test_main_passes_bridge_only_to_existing_safe_provisioner(self):
        with patch.object(office,'office_guard'),patch.object(provision,'prepare') as prepare:
            def reject(**kwargs):
                self.assertIs(kwargs['bridge_acceptance'],office.run_bridge)
                self.assertEqual(office.os.environ.get('V2_AAA_EXISTING_PG_TESTS'),'1')
                raise RuntimeError('NO_REAL_PROVISION_IN_UNIT_TEST')
            prepare.side_effect=reject
            with self.assertRaisesRegex(RuntimeError,'NO_REAL_PROVISION_IN_UNIT_TEST'):office.main()
