from django.test import TestCase, override_settings

from .models import IntegrationSyncRun
from .registry import get_plugin, list_plugins
from .services import execute_eam_sync


class IntegrationPluginTests(TestCase):
    def test_plugin_registry_contains_expected_plugins(self):
        plugins = list_plugins()
        self.assertIn({"plugin_name": "beam_web_service", "plugin_version": "v1"}, plugins)
        self.assertIn({"plugin_name": "excel_bootstrap", "plugin_version": "v1"}, plugins)

    def test_invalid_plugin_raises_value_error(self):
        with self.assertRaises(ValueError):
            get_plugin("unknown", "v1")

    @override_settings(EAM_PLUGIN_NAME="beam_web_service", EAM_PLUGIN_VERSION="v1", BEAM_LIVE_ENABLED=False)
    def test_execute_sync_uses_beam_offline_mode_until_live_window(self):
        sync_run = execute_eam_sync(direction=IntegrationSyncRun.DIRECTION_INBOUND)
        self.assertEqual(sync_run.status, IntegrationSyncRun.STATUS_SUCCESS)
        self.assertEqual(sync_run.plugin_name, "beam_web_service")
        self.assertEqual(sync_run.plugin_version, "v1")
        self.assertIn("offline", sync_run.message)
        self.assertIn("2026-02-25", sync_run.message)
