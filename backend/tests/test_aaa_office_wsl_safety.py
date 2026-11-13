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

    def test_office_runtime_preserves_wsl_identity_but_removes_external_pg_settings(self):
        with patch.dict(office.os.environ, {'WSL_DISTRO_NAME':'Ubuntu-24.04',
                                          'PGHOSTADDR':'external','PGOPTIONS':'external'}):
            with office.office_runtime():
                self.assertEqual(office.os.environ['WSL_DISTRO_NAME'],'Ubuntu-24.04')
                self.assertNotIn('PGHOSTADDR',office.os.environ)
                self.assertNotIn('PGOPTIONS',office.os.environ)
            self.assertEqual(office.os.environ['PGOPTIONS'],'external')

    def test_real_office_identity_recheck_survives_clean_runtime(self):
        # Deterministic Office identity; neither host allowlist nor kernel/venv
        # verification is skipped. Only git's branch/status reads are fixture values.
        with patch.object(office.platform,'node',return_value=office.HOST), \
                patch.object(office.Path,'cwd',return_value=office.REPO), \
                patch.object(office.Path,'read_text',return_value='Microsoft WSL kernel'), \
                patch.object(office.sys,'prefix',str(office.REPO/'.venv')), \
                patch.dict(office.os.environ,{'WSL_DISTRO_NAME':'Ubuntu-24.04'}), \
                patch.object(office.subprocess,'check_output',side_effect=['main-guncel\n','','main-guncel\n','']):
            office.office_guard()
            with office.office_runtime():office.office_guard()

    def test_missing_wsl_marker_not_reconstructed_or_guessed(self):
        with patch.dict(office.os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,'OFFICE_WSL_IDENTITY_REJECTED'):
                with office.office_runtime():pass

    def test_foreign_environment_label_denied_before_root_access(self):
        with patch.object(provision.os.path,'lexists') as root:
            with self.assertRaisesRegex(RuntimeError,'AAA_FIXTURE_ENVIRONMENT_REJECTED'):
                provision.prepare(environment='foreign')
            root.assert_not_called()

    def test_office_provision_label_is_explicit_and_existing_cluster_never_reused(self):
        with patch.object(office,'office_guard'), \
                patch.dict(office.os.environ,{'WSL_DISTRO_NAME':'Ubuntu-24.04'}), \
                patch.object(provision,'prepare') as prepare:
            prepare.side_effect=RuntimeError('PROVISION_NOT_RUN')
            with self.assertRaisesRegex(RuntimeError,'PROVISION_NOT_RUN'):office.main()
            self.assertEqual(prepare.call_args.kwargs['environment'],'OFFICE_WSL_AAA_FIXTURE')

    def test_existing_mode_never_calls_new_provisioner(self):
        with patch.object(office,'office_guard'),patch.dict(office.os.environ,{'WSL_DISTRO_NAME':'Ubuntu-24.04'}), \
                patch.object(office,'run_existing') as existing,patch.object(provision,'prepare') as create:
            existing.side_effect=RuntimeError('NO_REAL_START_IN_TEST')
            with self.assertRaisesRegex(RuntimeError,'NO_REAL_START_IN_TEST'):office.main(existing=True)
            existing.assert_called_once_with();create.assert_not_called()

    def test_existing_guard_error_never_starts_or_changes_cluster(self):
        with patch.object(office,'verify_existing_files',side_effect=RuntimeError('EXACT_OFFICE_CLUSTER_REQUIRED')), \
                patch.object(provision,'run_tool') as tool,patch.object(provision.socket,'socket') as socket:
            with self.assertRaisesRegex(RuntimeError,'EXACT_OFFICE_CLUSTER_REQUIRED'):office.run_existing()
            tool.assert_not_called();socket.assert_not_called()

    def test_existing_office_id_is_fixed_not_selected_by_environment(self):
        self.assertEqual(office.EXISTING_CLUSTER_ID,'7707521885424832975')
        with patch.dict(office.os.environ,{'V2_CLUSTER_ID':'7707358750625226262'}):
            self.assertEqual(office.EXISTING_CLUSTER_ID,'7707521885424832975')

    def test_existing_lifecycle_preserves_running_or_stopped_state_on_failure(self):
        for state in ('in production','shut down'):
            class Existing:
                stopped=0
                captured=0
                def verify_data(self):return provision.ROOT/'postgres-test'
                def capture_process(self):type(self).captured+=1
                def verify(self):pass
                def stop(self):type(self).stopped+=1
            manifest={'root_identity':(1,2,1000),'data_identity':(1,3,1000)}
            with patch.object(office,'verify_existing_files',return_value=(manifest,state)), \
                    patch.object(provision,'OwnedRoot',Existing),patch.object(office.os,'open',return_value=99), \
                    patch.object(office.os,'close'),patch.object(provision.socket,'socket'), \
                    patch.object(provision,'run_tool') as start, \
                    patch.object(office,'run_bridge',side_effect=RuntimeError('NO_PG_TEST_IN_UNIT_TEST')):
                with self.assertRaisesRegex(RuntimeError,'NO_PG_TEST_IN_UNIT_TEST'):office.run_existing()
                self.assertEqual(Existing.captured,1)
                self.assertEqual(Existing.stopped,1 if state=='shut down' else 0)
                self.assertEqual(start.call_count,1 if state=='shut down' else 0)
