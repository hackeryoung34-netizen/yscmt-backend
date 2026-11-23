from django.test import TestCase
from rest_framework.test import APIClient
from .models import PortalIdentity, PortalCourse, PortalLesson, PortalEnrollment

class StudentPortalAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = PortalIdentity(username="student1", email="student1@example.test")
        self.student.set_password("StrongPass!2026")
        self.student.save()
        self.other = PortalIdentity(username="student2", email="student2@example.test")
        self.other.set_password("StrongPass!2026")
        self.other.save()
        self.course = PortalCourse.objects.create(title="Python Fundamentals")
        self.lesson = PortalLesson.objects.create(course=self.course, title="Lesson 1", content="Synthetic lesson")
    
    def token_for(self, username):
        response = self.client.post("/api/token/", {"username": username, "password": "StrongPass!2026"}, format="json")
        self.assertEqual(response.status_code, 200)
        return response.data["access"]

    def test_registration_creates_student_only(self):
        response = self.client.post("/api/auth/register/", {"username": "newstudent", "email": "new@example.test", "password": "UniqueStrong!2026"}, format="json")
        self.assertEqual(response.status_code, 201)
        identity = PortalIdentity.objects.get(username="newstudent")
        self.assertEqual(identity.role, PortalIdentity.ROLE_STUDENT)
        self.assertTrue(identity.check_password("UniqueStrong!2026"))

    def test_login_and_profile(self):
        token = self.token_for("student1")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/portal/v1/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.student.pk))

    def test_course_catalog_requires_authentication(self):
        self.assertEqual(self.client.get("/api/portal/v1/courses/").status_code, 401)

    def test_enrollment_is_pending_and_duplicate_is_rejected(self):
        token = self.token_for("student1")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        first = self.client.post("/api/portal/v1/enrollments/", {"course_id": str(self.course.pk)}, format="json")
        second = self.client.post("/api/portal/v1/enrollments/", {"course_id": str(self.course.pk)}, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["status"], "pending")
        self.assertEqual(second.status_code, 409)

    def test_unapproved_student_cannot_read_lessons(self):
        token = self.token_for("student1")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.PENDING)
        response = self.client.get(f"/api/portal/v1/courses/{self.course.pk}/lessons/")
        self.assertEqual(response.status_code, 403)

    def test_only_approved_enrollment_can_read_lessons(self):
        token = self.token_for("student1")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.APPROVED)
        response = self.client.get(f"/api/portal/v1/courses/{self.course.pk}/lessons/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_progress_requires_approved_enrollment_and_is_idempotent(self):
        token = self.token_for("student1")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        denied = self.client.post(f"/api/portal/v1/lessons/{self.lesson.pk}/complete/")
        self.assertEqual(denied.status_code, 403)
        PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.APPROVED)
        first = self.client.post(f"/api/portal/v1/lessons/{self.lesson.pk}/complete/")
        second = self.client.post(f"/api/portal/v1/lessons/{self.lesson.pk}/complete/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["completed_at"], second.data["completed_at"])
        progress = self.client.get(f"/api/portal/v1/courses/{self.course.pk}/progress/")
        self.assertEqual(progress.data, {"total_lessons": 1, "completed_lessons": 1, "progress_percent": 100})
