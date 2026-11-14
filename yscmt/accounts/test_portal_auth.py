import json
from unittest.mock import Mock, patch
from uuid import UUID

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from .portal_auth import SupabasePortalAuthentication, PortalPrincipal


@override_settings(
    SUPABASE_URL="https://example-project.supabase.co",
    SUPABASE_PUBLISHABLE_KEY="sb_publishable_test_key",
)
class SupabasePortalAuthenticationTests(SimpleTestCase):
    def setUp(self):
        self.auth = SupabasePortalAuthentication()
        self.request = Mock()
        self.request.headers = {"Authorization": "Bearer test-user-token"}

    @patch("accounts.portal_auth.requests.post")
    def test_returns_trusted_student_identity(self, post):
        response = Mock()
        response.status_code = 200
        response.raw.read.return_value = json.dumps([{
            "user_id": "7e3f65a2-72e9-4f0f-9a93-4e7d5b123456",
            "email": "student@example.com",
            "role": "student",
            "full_name": "Test Student",
            "phone": "+2348000000000",
        }]).encode()
        post.return_value = response

        principal, auth = self.auth.authenticate(self.request)

        self.assertIsInstance(principal, PortalPrincipal)
        self.assertEqual(principal.id, UUID("7e3f65a2-72e9-4f0f-9a93-4e7d5b123456"))
        self.assertEqual(principal.role, "student")
        self.assertEqual(principal.email, "student@example.com")
        self.assertTrue(principal.is_authenticated)
        self.assertEqual(auth["provider"], "supabase")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-user-token")
        self.assertEqual(kwargs["headers"]["apikey"], "sb_publishable_test_key")
        self.assertTrue(kwargs["endpoint"] if "endpoint" in kwargs else post.call_args.args[0].endswith("/rest/v1/rpc/portal_get_my_identity"))

    @patch("accounts.portal_auth.requests.post")
    def test_rejects_missing_identity(self, post):
        response = Mock()
        response.status_code = 200
        response.raw.read.return_value = b"[]"
        post.return_value = response
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(self.request)

    @patch("accounts.portal_auth.requests.post")
    def test_rejects_invalid_role(self, post):
        response = Mock()
        response.status_code = 200
        response.raw.read.return_value = json.dumps([{
            "user_id": "7e3f65a2-72e9-4f0f-9a93-4e7d5b123456",
            "email": "student@example.com",
            "role": "superadmin",
        }]).encode()
        post.return_value = response
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(self.request)

    def test_missing_header_is_anonymous(self):
        self.request.headers = {}
        self.assertIsNone(self.auth.authenticate(self.request))
