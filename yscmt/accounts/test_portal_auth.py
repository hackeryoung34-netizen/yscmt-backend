import json
from unittest.mock import Mock, patch
from uuid import UUID

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from .portal_auth import SupabasePortalAuthentication, PortalPrincipal
from .portal_permissions import IsPortalAdmin, IsPortalStudent
from .portal_views import PortalMeAPIView


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
        self.assertTrue(post.call_args.args[0].endswith("/rest/v1/rpc/portal_get_my_identity"))

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

    @patch("accounts.portal_auth.requests.post")
    def test_portal_me_endpoint_returns_only_verified_identity(self, post):
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

        request = APIRequestFactory().get(
            "/api/portal/v1/me/",
            HTTP_AUTHORIZATION="Bearer test-user-token",
        )
        result = PortalMeAPIView.as_view()(request)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["role"], "student")
        self.assertEqual(result.data["email"], "student@example.com")
        self.assertNotIn("password", result.data)
        self.assertNotIn("access_token", result.data)

    def test_portal_me_endpoint_rejects_missing_token(self):
        request = APIRequestFactory().get("/api/portal/v1/me/")
        result = PortalMeAPIView.as_view()(request)
        self.assertEqual(result.status_code, 401)

    @patch("accounts.portal_auth.requests.post")
    def test_identity_service_error_fails_closed(self, post):
        response = Mock()
        response.status_code = 500
        response.raw.read.return_value = b'{"error":"internal"}'
        post.return_value = response

        from .portal_auth import IdentityServiceUnavailable
        with self.assertRaises(IdentityServiceUnavailable):
            self.auth.authenticate(self.request)
        response.close.assert_called_once()

    @patch("accounts.portal_auth.requests.post")
    def test_oversized_identity_response_fails_closed(self, post):
        response = Mock()
        response.status_code = 200
        response.raw.read.return_value = b"x" * (self.auth.max_response_bytes + 1)
        post.return_value = response

        from .portal_auth import IdentityServiceUnavailable
        with self.assertRaises(IdentityServiceUnavailable):
            self.auth.authenticate(self.request)
        response.close.assert_called_once()

    @patch("accounts.portal_auth.requests.post")
    def test_malformed_identity_payload_fails_closed(self, post):
        response = Mock()
        response.status_code = 200
        response.raw.read.return_value = b"not-json"
        post.return_value = response

        from .portal_auth import IdentityServiceUnavailable
        with self.assertRaises(IdentityServiceUnavailable):
            self.auth.authenticate(self.request)

    @patch("accounts.portal_auth.requests.post")
    def test_expired_token_is_rejected(self, post):
        response = Mock()
        response.status_code = 401
        response.raw.read.return_value = b"{}"
        post.return_value = response

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(self.request)

    def test_instructor_role_cannot_access_admin_permission(self):
        principal = PortalPrincipal(
            id=UUID("7e3f65a2-72e9-4f0f-9a93-4e7d5b123456"),
            email="instructor@example.com",
            role="instructor",
            full_name="Test Instructor",
            phone="",
        )
        request = Mock()
        request.user = principal
        self.assertFalse(IsPortalAdmin().has_permission(request, None))

    @patch("accounts.portal_views.call_portal_rpc")
    def test_student_course_list_uses_scoped_rpc(self, rpc):
        from .portal_views import PortalCourseListAPIView
        principal = PortalPrincipal(
            id=UUID("7e3f65a2-72e9-4f0f-9a93-4e7d5b123456"),
            email="student@example.com",
            role="student",
            full_name="Test Student",
            phone="",
        )
        rpc.return_value = [{
            "id": "c8b56b9d-7199-4e6f-8a22-4a2f8c3c1234",
            "title": "Python Basics",
            "enrollment_status": "approved",
        }]
        request = APIRequestFactory().get(
            "/api/portal/v1/courses/",
            HTTP_AUTHORIZATION="Bearer test-user-token",
        )
        from rest_framework.test import force_authenticate
        force_authenticate(request, user=principal)
        result = PortalCourseListAPIView.as_view()(request)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["results"][0]["title"], "Python Basics")
        rpc.assert_called_once()
        self.assertEqual(rpc.call_args.args[1], "portal_list_courses")
        self.assertEqual(rpc.call_args.args[0].headers["Authorization"], "Bearer test-user-token")

    @patch("accounts.portal_views.call_portal_rpc")
    def test_course_lessons_are_requested_through_gated_rpc(self, rpc):
        from .portal_views import PortalCourseLessonsAPIView
        principal = PortalPrincipal(
            id=UUID("7e3f65a2-72e9-4f0f-9a93-4e7d5b123456"),
            email="student@example.com",
            role="student",
            full_name="Test Student",
            phone="",
        )
        rpc.return_value = []
        course_id = UUID("c8b56b9d-7199-4e6f-8a22-4a2f8c3c1234")
        request = APIRequestFactory().get(
            f"/api/portal/v1/courses/{course_id}/lessons/",
            HTTP_AUTHORIZATION="Bearer test-user-token",
        )
        from rest_framework.test import force_authenticate
        force_authenticate(request, user=principal)
        result = PortalCourseLessonsAPIView.as_view()(request, course_id=course_id)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["results"], [])
        rpc.assert_called_once()
        self.assertEqual(rpc.call_args.args[1], "portal_get_course_lessons")
        self.assertEqual(rpc.call_args.args[2], {"p_course_id": str(course_id)})

    @patch("accounts.portal_views.call_portal_rpc")
    def test_instructor_is_denied_student_course_catalogue(self, rpc):
        from .portal_views import PortalCourseListAPIView
        principal = PortalPrincipal(
            id=UUID("7e3f65a2-72e9-4f0f-9a93-4e7d5b123456"),
            email="instructor@example.com",
            role="instructor",
            full_name="Test Instructor",
            phone="",
        )
        request = APIRequestFactory().get("/api/portal/v1/courses/")
        from rest_framework.test import force_authenticate
        force_authenticate(request, user=principal)
        result = PortalCourseListAPIView.as_view()(request)

        self.assertEqual(result.status_code, 403)
        rpc.assert_not_called()

    def test_student_role_cannot_access_admin_permission(self):
        principal = PortalPrincipal(
            id=UUID("7e3f65a2-72e9-4f0f-9a93-4e7d5b123456"),
            email="student@example.com",
            role="student",
            full_name="Test Student",
            phone="",
        )
        request = Mock()
        request.user = principal
        self.assertTrue(IsPortalStudent().has_permission(request, None))
        self.assertFalse(IsPortalAdmin().has_permission(request, None))

    @patch("accounts.portal_views.call_portal_rpc")
    def test_student_can_create_only_pending_enrolment(self, rpc):
        from .portal_views import PortalEnrollmentCreateAPIView
        from rest_framework.test import force_authenticate

        principal = PortalPrincipal(
            id=UUID("7e3f65a2-72e9-4f0f-9a93-4e7d5b123456"),
            email="student@example.com",
            role="student",
            full_name="Test Student",
            phone="",
        )
        course_id = UUID("c8b56b9d-7199-4e6f-8a22-4a2f8c3c1234")
        rpc.return_value = [{
            "id": "f1a7e5d3-5f52-4b0d-92c4-7c83fda3d6a1",
            "course_id": str(course_id),
            "status": "pending",
            "enrolled_at": "2026-11-14T12:00:00Z",
        }]
        request = APIRequestFactory().post(
            "/api/portal/v1/enrollments/",
            {"course_id": str(course_id), "status": "approved", "user_id": "other"},
            format="json",
            HTTP_AUTHORIZATION="Bearer test-user-token",
        )
        force_authenticate(request, user=principal)
        result = PortalEnrollmentCreateAPIView.as_view()(request)

        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data["status"], "pending")
        rpc.assert_called_once()
        self.assertEqual(rpc.call_args.args[1], "portal_create_enrollment")
        self.assertEqual(rpc.call_args.args[2], {"p_course_id": str(course_id)})

    @patch("accounts.portal_views.call_portal_rpc")
    def test_student_enrolment_rejects_invalid_course_uuid(self, rpc):
        from .portal_views import PortalEnrollmentCreateAPIView
        from rest_framework.test import force_authenticate

        principal = PortalPrincipal(
            id=UUID("7e3f65a2-72e9-4f0f-9a93-4e7d5b123456"),
            email="student@example.com",
            role="student",
            full_name="Test Student",
            phone="",
        )
        request = APIRequestFactory().post(
            "/api/portal/v1/enrollments/",
            {"course_id": "not-a-uuid"},
            format="json",
        )
        force_authenticate(request, user=principal)
        result = PortalEnrollmentCreateAPIView.as_view()(request)

        self.assertEqual(result.status_code, 400)
        rpc.assert_not_called()

    @patch("accounts.portal_views.call_portal_rpc")
    def test_instructor_cannot_create_student_enrolment(self, rpc):
        from .portal_views import PortalEnrollmentCreateAPIView
        from rest_framework.test import force_authenticate

        principal = PortalPrincipal(
            id=UUID("7e3f65a2-72e9-4f0f-9a93-4e7d5b123456"),
            email="instructor@example.com",
            role="instructor",
            full_name="Test Instructor",
            phone="",
        )
        request = APIRequestFactory().post(
            "/api/portal/v1/enrollments/",
            {"course_id": "c8b56b9d-7199-4e6f-8a22-4a2f8c3c1234"},
            format="json",
        )
        force_authenticate(request, user=principal)
        result = PortalEnrollmentCreateAPIView.as_view()(request)

        self.assertEqual(result.status_code, 403)
        rpc.assert_not_called()
