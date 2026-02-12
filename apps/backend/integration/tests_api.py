from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class IntegrationApiPermissionTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(username="sync_admin", password="pass1234")
        self.viewer_user = user_model.objects.create_user(username="sync_viewer", password="pass1234")

        admin_group, _ = Group.objects.get_or_create(name="risk_admin")
        self.admin_user.groups.add(admin_group)

    def test_non_admin_cannot_run_sync(self):
        self.client.force_authenticate(self.viewer_user)
        response = self.client.post(
            reverse("integration-eam-sync"),
            data={"direction": "inbound", "plugin_name": "beam_web_service", "plugin_version": "v1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(BEAM_LIVE_ENABLED=False)
    def test_admin_can_run_sync(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.post(
            reverse("integration-eam-sync"),
            data={"direction": "inbound", "plugin_name": "beam_web_service", "plugin_version": "v1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
