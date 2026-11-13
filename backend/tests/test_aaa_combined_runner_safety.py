from unittest import TestCase
from unittest.mock import patch
from backend.tests import run_aaa_combined_postgres as runner


class FreshRunnerSafety(TestCase):
    def test_existing_root_never_provisions_or_connects(self):
        with patch.object(runner.provision,'home_guard'), patch.object(runner.os.path,'lexists',return_value=True), \
                patch.object(runner.provision,'prepare') as prepare:
            with self.assertRaisesRegex(RuntimeError,'^ACCEPTANCE_ROOT_ALREADY_EXISTS$'): runner.main()
            prepare.assert_not_called()

    def test_wrong_environment_never_provisions(self):
        with patch.object(runner.provision,'home_guard',side_effect=RuntimeError('HOME_WSL_IDENTITY_REJECTED')), \
                patch.object(runner.provision,'prepare') as prepare:
            with self.assertRaisesRegex(RuntimeError,'^HOME_WSL_IDENTITY_REJECTED$'): runner.main()
            prepare.assert_not_called()
