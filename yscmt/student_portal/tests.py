from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import PortalIdentity, PortalCourse, PortalLesson, PortalEnrollment, PortalExam, PortalExamQuestion, PortalExamSession, PortalExamAttempt

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


    def make_exam(self):
        exam = PortalExam.objects.create(
            course=self.course,
            title="Python Basics Exam",
            instructions="Choose the best answer.",
            duration_minutes=30,
            pass_mark=50,
            is_active=True,
        )
        q1 = PortalExamQuestion.objects.create(
            exam=exam, question_text="Which is a Python type?",
            options=["int", "table", "page", "sheet"], correct_option=0, sort_order=1,
        )
        q2 = PortalExamQuestion.objects.create(
            exam=exam, question_text="Which keyword defines a function?",
            options=["class", "def", "loop", "func"], correct_option=1, sort_order=2,
        )
        return exam, q1, q2

    def approve_student(self):
        PortalEnrollment.objects.create(
            student=self.student, course=self.course, status=PortalEnrollment.APPROVED
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")

    def test_exam_catalogue_requires_approved_enrollment(self):
        exam, _, _ = self.make_exam()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        denied = self.client.get(f"/api/portal/v1/courses/{self.course.pk}/exams/")
        self.assertEqual(denied.status_code, 403)
        PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.APPROVED)
        allowed = self.client.get(f"/api/portal/v1/courses/{self.course.pk}/exams/")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.data["results"][0]["id"], str(exam.pk))

    def test_exam_question_delivery_never_exposes_answer_key(self):
        exam, q1, q2 = self.make_exam()
        self.approve_student()
        started = self.client.post(f"/api/portal/v1/exams/{exam.pk}/start/", {}, format="json")
        self.assertEqual(started.status_code, 201)
        response = self.client.get(
            f"/api/portal/v1/exam-sessions/{started.data['session_id']}/questions/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertNotIn("correct_option", response.data["results"][0])
        self.assertNotIn("answers", response.data["results"][0])

    def test_exam_start_resumes_one_active_session(self):
        exam, _, _ = self.make_exam()
        self.approve_student()
        first = self.client.post(f"/api/portal/v1/exams/{exam.pk}/start/", {}, format="json")
        second = self.client.post(f"/api/portal/v1/exams/{exam.pk}/start/", {}, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["session_id"], second.data["session_id"])
        self.assertTrue(second.data["resumed"])
        self.assertEqual(PortalExamSession.objects.filter(exam=exam, student=self.student, submitted_at__isnull=True).count(), 1)

    def test_exam_submission_is_scored_server_side_and_idempotent(self):
        exam, q1, q2 = self.make_exam()
        self.approve_student()
        started = self.client.post(f"/api/portal/v1/exams/{exam.pk}/start/", {}, format="json")
        session_id = started.data["session_id"]
        answers = {str(q1.pk): 0, str(q2.pk): 1}
        first = self.client.post(
            f"/api/portal/v1/exam-sessions/{session_id}/submit/",
            {"answers": answers}, format="json",
        )
        second = self.client.post(
            f"/api/portal/v1/exam-sessions/{session_id}/submit/",
            {"answers": answers}, format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["score"], 100)
        self.assertTrue(first.data["passed"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["attempt_id"], second.data["attempt_id"])
        self.assertEqual(PortalExamAttempt.objects.filter(session_id=session_id).count(), 1)

    def test_exam_submission_requires_exact_question_set(self):
        exam, q1, q2 = self.make_exam()
        self.approve_student()
        started = self.client.post(f"/api/portal/v1/exams/{exam.pk}/start/", {}, format="json")
        response = self.client.post(
            f"/api/portal/v1/exam-sessions/{started.data['session_id']}/submit/",
            {"answers": {str(q1.pk): 0}}, format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PortalExamAttempt.objects.count(), 0)

    def test_student_cannot_read_another_students_exam_session(self):
        exam, _, _ = self.make_exam()
        self.approve_student()
        started = self.client.post(f"/api/portal/v1/exams/{exam.pk}/start/", {}, format="json")
        other_token = self.token_for("student2")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_token}")
        response = self.client.get(
            f"/api/portal/v1/exam-sessions/{started.data['session_id']}/questions/"
        )
        self.assertEqual(response.status_code, 404)

    def test_expired_exam_session_is_recorded_as_failed_attempt(self):
        exam, q1, q2 = self.make_exam()
        self.approve_student()
        started = self.client.post(f"/api/portal/v1/exams/{exam.pk}/start/", {}, format="json")
        session = PortalExamSession.objects.get(pk=started.data["session_id"])
        session.started_at = timezone.now() - timedelta(minutes=31)
        session.save(update_fields=["started_at"])

        questions = self.client.get(
            f"/api/portal/v1/exam-sessions/{session.pk}/questions/"
        )
        self.assertEqual(questions.status_code, 410)

        submitted = self.client.post(
            f"/api/portal/v1/exam-sessions/{session.pk}/submit/",
            {"answers": {str(q1.pk): 0, str(q2.pk): 1}}, format="json",
        )
        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(submitted.data["score"], 0)
        self.assertFalse(submitted.data["passed"])
        self.assertEqual(PortalExamAttempt.objects.filter(session=session).count(), 1)
