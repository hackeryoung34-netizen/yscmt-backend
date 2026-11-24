from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import PortalIdentity, PortalCourse, PortalCourseInstructor, PortalLesson, PortalEnrollment, PortalExam, PortalExamQuestion, PortalExamSession, PortalExamAttempt, PortalPayment, PortalPaymentSubmission, PortalCertificate, PortalPracticeSubmission, PortalClassroomSession, PortalClassroomAttendance, PortalClassroomMessage, PortalClassroomAnnouncement, PortalTeacherReply

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

    def test_payment_initialization_uses_stored_fee_not_client_amount(self):
        self.course.fee_amount = Decimal("15000.00")
        self.course.fee_currency = "NGN"
        self.course.save()
        enrollment = PortalEnrollment.objects.create(
            student=self.student, course=self.course, status=PortalEnrollment.PENDING
        )
        PortalPayment.objects.create(
            enrollment=enrollment, student=self.student,
            reference="YSCMT_TEST_REFERENCE", amount_kobo=1500000, currency="NGN",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        gateway = Mock(status_code=200)
        gateway.json.return_value = {
            "status": True,
            "data": {
                "reference": "YSCMT_TEST_REFERENCE",
                "authorization_url": "https://checkout.paystack.com/example",
            },
        }
        with patch.dict("os.environ", {"PAYSTACK_SECRET_KEY": "sk_test_example", "PAYSTACK_EXPECTED_DOMAIN": "test"}):
            with patch("student_portal.views.requests.post", return_value=gateway) as post:
                response = self.client.post(
                    f"/api/portal/v1/enrollments/{enrollment.pk}/payments/initialize/",
                    {"amount": 1, "currency": "USD"}, format="json",
                )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["amount_kobo"], 1500000)
        self.assertEqual(response.data["currency"], "NGN")
        self.assertEqual(post.call_args.kwargs["json"]["amount"], 1500000)
        self.assertEqual(post.call_args.kwargs["json"]["currency"], "NGN")
        self.assertEqual(PortalPayment.objects.get(enrollment=enrollment).status, PortalPayment.PENDING)

    def test_payment_verification_approves_enrollment_only_after_gateway_success(self):
        self.course.fee_amount = Decimal("15000.00")
        self.course.fee_currency = "NGN"
        self.course.save()
        enrollment = PortalEnrollment.objects.create(
            student=self.student, course=self.course, status=PortalEnrollment.PENDING
        )
        payment = PortalPayment.objects.create(
            enrollment=enrollment, student=self.student,
            reference="YSCMT_VERIFY_REFERENCE", amount_kobo=1500000, currency="NGN",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        gateway = Mock(status_code=200)
        gateway.json.return_value = {
            "status": True,
            "data": {
                "status": "success",
                "reference": payment.reference,
                "amount": 1500000,
                "currency": "NGN",
                "domain": "test",
                "paid_at": "2026-11-24T06:00:00.000Z",
                "channel": "card",
                "id": 123456,
            },
        }
        with patch.dict("os.environ", {"PAYSTACK_SECRET_KEY": "sk_test_example", "PAYSTACK_EXPECTED_DOMAIN": "test"}):
            with patch("student_portal.views.requests.get", return_value=gateway):
                response = self.client.post(
                    f"/api/portal/v1/payments/{payment.reference}/verify/", {}, format="json"
                )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        enrollment.refresh_from_db()
        self.assertEqual(payment.status, PortalPayment.SUCCESS)
        self.assertEqual(enrollment.status, PortalEnrollment.APPROVED)
        self.assertIsNotNone(payment.verified_at)

    def test_payment_verification_rejects_amount_mismatch(self):
        self.course.fee_amount = Decimal("15000.00")
        self.course.fee_currency = "NGN"
        self.course.save()
        enrollment = PortalEnrollment.objects.create(
            student=self.student, course=self.course, status=PortalEnrollment.PENDING
        )
        payment = PortalPayment.objects.create(
            enrollment=enrollment, student=self.student,
            reference="YSCMT_BAD_AMOUNT", amount_kobo=1500000, currency="NGN",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        gateway = Mock(status_code=200)
        gateway.json.return_value = {
            "status": True,
            "data": {
                "status": "success", "reference": payment.reference,
                "amount": 1, "currency": "NGN", "domain": "test",
            },
        }
        with patch.dict("os.environ", {"PAYSTACK_SECRET_KEY": "sk_test_example", "PAYSTACK_EXPECTED_DOMAIN": "test"}):
            with patch("student_portal.views.requests.get", return_value=gateway):
                response = self.client.post(
                    f"/api/portal/v1/payments/{payment.reference}/verify/", {}, format="json"
                )
        self.assertEqual(response.status_code, 400)
        payment.refresh_from_db()
        enrollment.refresh_from_db()
        self.assertEqual(payment.status, PortalPayment.PENDING)
        self.assertEqual(enrollment.status, PortalEnrollment.PENDING)

    def test_payment_initialization_fails_closed_without_gateway_secret(self):
        self.course.fee_amount = Decimal("1000.00")
        self.course.fee_currency = "NGN"
        self.course.save()
        enrollment = PortalEnrollment.objects.create(
            student=self.student, course=self.course, status=PortalEnrollment.PENDING
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        with patch.dict("os.environ", {"PAYSTACK_SECRET_KEY": "", "PAYSTACK_EXPECTED_DOMAIN": ""}):
            response = self.client.post(
                f"/api/portal/v1/enrollments/{enrollment.pk}/payments/initialize/", {}, format="json"
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(PortalPayment.objects.count(), 0)

    def test_payment_initialization_creates_secure_reference_for_new_intent(self):
        self.course.fee_amount = Decimal("2500.00")
        self.course.fee_currency = "NGN"
        self.course.save()
        enrollment = PortalEnrollment.objects.create(
            student=self.student, course=self.course, status=PortalEnrollment.PENDING
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        gateway = Mock(status_code=200)
        with patch.dict("os.environ", {"PAYSTACK_SECRET_KEY": "sk_test_example", "PAYSTACK_EXPECTED_DOMAIN": "test"}):
            with patch("student_portal.views.requests.post") as post:
                post.return_value = gateway
                gateway.json.side_effect = lambda: {
                    "status": True,
                    "data": {
                        "reference": post.call_args.kwargs["json"]["reference"],
                        "authorization_url": "https://checkout.paystack.com/new-example",
                    },
                }
                response = self.client.post(
                    f"/api/portal/v1/enrollments/{enrollment.pk}/payments/initialize/",
                    {}, format="json",
                )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["reference"].startswith("YSCMT_"))
        self.assertEqual(response.data["amount_kobo"], 250000)
        self.assertEqual(PortalPayment.objects.filter(enrollment=enrollment).count(), 1)

    def test_certificate_requires_full_course_completion_and_passed_exam(self):
        exam, _, _ = self.make_exam()
        self.approve_student()
        denied_lessons = self.client.post(
            f"/api/portal/v1/courses/{self.course.pk}/certificates/request/", {}, format="json"
        )
        self.assertEqual(denied_lessons.status_code, 400)

        completed = self.client.post(f"/api/portal/v1/lessons/{self.lesson.pk}/complete/")
        self.assertEqual(completed.status_code, 200)
        denied_exam = self.client.post(
            f"/api/portal/v1/courses/{self.course.pk}/certificates/request/", {}, format="json"
        )
        self.assertEqual(denied_exam.status_code, 400)

        session = PortalExamSession.objects.create(exam=exam, student=self.student)
        now = timezone.now()
        PortalExamAttempt.objects.create(
            session=session, exam=exam, student=self.student, answers={},
            score=100, passed=True, started_at=session.started_at, submitted_at=now,
        )
        session.submitted_at = now
        session.save(update_fields=["submitted_at"])

        issued = self.client.post(
            f"/api/portal/v1/courses/{self.course.pk}/certificates/request/", {}, format="json"
        )
        repeated = self.client.post(
            f"/api/portal/v1/courses/{self.course.pk}/certificates/request/", {}, format="json"
        )
        self.assertEqual(issued.status_code, 201)
        self.assertEqual(repeated.status_code, 201)
        self.assertEqual(issued.data["certificate_code"], repeated.data["certificate_code"])
        self.assertEqual(PortalCertificate.objects.filter(student=self.student, course=self.course).count(), 1)

        listing = self.client.get("/api/portal/v1/certificates/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data["results"]), 1)
        verification = self.client.get(
            f"/api/portal/v1/certificates/verify/{issued.data['certificate_code'].lower()}/"
        )
        self.assertEqual(verification.status_code, 200)
        self.assertTrue(verification.data["valid"])
        self.assertEqual(verification.data["student_name"], self.student.full_name or "YSCMT Student")

    def test_classroom_sessions_require_enrollment_and_join_is_idempotent(self):
        self.approve_student()
        now = timezone.now()
        session = PortalClassroomSession.objects.create(
            course=self.course, title="Live Python Class",
            meeting_url="https://meet.example.test/python",
            starts_at=now + timedelta(minutes=10),
            ends_at=now + timedelta(minutes=70),
            status="scheduled",
        )
        listed = self.client.get(f"/api/portal/v1/courses/{self.course.pk}/classroom/sessions/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data["results"]), 1)
        first = self.client.post(f"/api/portal/v1/classroom/sessions/{session.pk}/join/")
        second = self.client.post(f"/api/portal/v1/classroom/sessions/{session.pk}/join/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["attendance_id"], second.data["attendance_id"])
        self.assertEqual(PortalClassroomAttendance.objects.filter(session=session, student=self.student).count(), 1)

    def test_classroom_message_requires_approved_enrollment_and_sets_student_role(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        denied = self.client.post(
            f"/api/portal/v1/courses/{self.course.pk}/classroom/messages/",
            {"message": "Hello class"}, format="json",
        )
        self.assertEqual(denied.status_code, 403)
        PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.APPROVED)
        sent = self.client.post(
            f"/api/portal/v1/courses/{self.course.pk}/classroom/messages/",
            {"message": "  Hello class  "}, format="json",
        )
        self.assertEqual(sent.status_code, 201)
        self.assertEqual(sent.data["message"], "Hello class")
        message = PortalClassroomMessage.objects.get(pk=sent.data["id"])
        self.assertEqual(message.author_role, "student")
        listed = self.client.get(f"/api/portal/v1/courses/{self.course.pk}/classroom/messages/")
        self.assertEqual(listed.data["results"][0]["id"], str(message.pk))

    def test_global_announcements_are_visible_but_course_announcements_are_gated(self):
        PortalClassroomAnnouncement.objects.create(title="General notice", body="Welcome")
        PortalClassroomAnnouncement.objects.create(
            course=self.course, title="Course notice", body="Approved students only"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        response = self.client.get(
            f"/api/portal/v1/courses/{self.course.pk}/classroom/announcements/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["title"] for item in response.data["results"]], ["General notice"])
        PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.APPROVED)
        enrolled = self.client.get(
            f"/api/portal/v1/courses/{self.course.pk}/classroom/announcements/"
        )
        self.assertEqual({item["title"] for item in enrolled.data["results"]}, {"General notice", "Course notice"})

    def test_practice_submission_requires_enrollment_and_keeps_owner_scope(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        denied = self.client.post(
            "/api/portal/v1/practice/submissions/",
            {"lab_key": "linux-01", "title": "Linux Lab"}, format="json",
        )
        self.assertEqual(denied.status_code, 403)
        PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.APPROVED)
        invalid_url = self.client.post(
            "/api/portal/v1/practice/submissions/",
            {"lab_key": "linux-01", "title": "Linux Lab", "project_url": "http://example.test"},
            format="json",
        )
        self.assertEqual(invalid_url.status_code, 400)
        submitted = self.client.post(
            "/api/portal/v1/practice/submissions/",
            {"lab_key": "linux-01", "title": "Linux Lab", "submission_text": "Completed", "project_url": "https://example.test/project"},
            format="json",
        )
        self.assertEqual(submitted.status_code, 201)
        listing = self.client.get("/api/portal/v1/practice/submissions/")
        self.assertEqual(len(listing.data["results"]), 1)
        self.assertEqual(listing.data["results"][0]["id"], submitted.data["id"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student2')}")
        other_listing = self.client.get("/api/portal/v1/practice/submissions/")
        self.assertEqual(other_listing.data["results"], [])

    def test_admin_can_review_enrollment_and_action_is_audited(self):
        enrollment = PortalEnrollment.objects.create(
            student=self.student, course=self.course, status=PortalEnrollment.PENDING
        )
        admin = PortalIdentity(username="portaladmin", email="admin@example.test", role=PortalIdentity.ROLE_ADMIN)
        admin.set_password("StrongPass!2026")
        admin.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('portaladmin')}")
        denied = self.client.get("/api/portal/v1/admin/enrollments/")
        self.assertEqual(denied.status_code, 200)
        changed = self.client.post(
            f"/api/portal/v1/admin/enrollments/{enrollment.pk}/review/",
            {"status": "approved"}, format="json",
        )
        self.assertEqual(changed.status_code, 200)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, PortalEnrollment.APPROVED)
        from .models import PortalAuditLog
        event = PortalAuditLog.objects.get(target_id=str(enrollment.pk))
        self.assertEqual(event.action, "enrollment.status_changed")
        self.assertEqual(event.metadata["to"], "approved")

    def test_student_cannot_access_admin_review_or_audit_logs(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        self.assertEqual(self.client.get("/api/portal/v1/admin/enrollments/").status_code, 403)
        self.assertEqual(self.client.get("/api/portal/v1/admin/audit-logs/").status_code, 403)



    def test_admin_cannot_mark_enrollment_completed_before_course_requirements(self):
        enrollment = PortalEnrollment.objects.create(
            student=self.student, course=self.course, status=PortalEnrollment.APPROVED
        )
        admin = PortalIdentity(username="completionadmin", email="completionadmin@example.test", role=PortalIdentity.ROLE_ADMIN)
        admin.set_password("StrongPass!2026")
        admin.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('completionadmin')}")
        response = self.client.post(
            f"/api/portal/v1/admin/enrollments/{enrollment.pk}/review/",
            {"status": "completed"}, format="json",
        )
        self.assertEqual(response.status_code, 400)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, PortalEnrollment.APPROVED)

    def test_admin_cannot_review_own_enrollment(self):
        admin = PortalIdentity(username="selfadmin", email="selfadmin@example.test", role=PortalIdentity.ROLE_ADMIN)
        admin.set_password("StrongPass!2026")
        admin.save()
        enrollment = PortalEnrollment.objects.create(
            student=admin, course=self.course, status=PortalEnrollment.PENDING
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('selfadmin')}")
        response = self.client.post(
            f"/api/portal/v1/admin/enrollments/{enrollment.pk}/review/",
            {"status": "approved"}, format="json",
        )
        self.assertEqual(response.status_code, 403)


    def test_admin_dashboard_and_student_list_are_role_protected(self):
        admin = PortalIdentity(username="dashboardadmin", email="dashboardadmin@example.test", role=PortalIdentity.ROLE_ADMIN)
        admin.set_password("StrongPass!2026")
        admin.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('dashboardadmin')}")
        overview = self.client.get("/api/portal/v1/admin/overview/")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.data["students_count"], 2)
        students = self.client.get("/api/portal/v1/admin/students/")
        self.assertEqual(students.status_code, 200)
        self.assertEqual(len(students.data["results"]), 2)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        self.assertEqual(self.client.get("/api/portal/v1/admin/overview/").status_code, 403)


    def test_admin_assigns_instructor_and_instructor_sees_only_assigned_courses(self):
        instructor = PortalIdentity(username="teacher1", email="teacher1@example.test", role=PortalIdentity.ROLE_INSTRUCTOR)
        instructor.set_password("StrongPass!2026")
        instructor.save()
        admin = PortalIdentity(username="assignadmin", email="assignadmin@example.test", role=PortalIdentity.ROLE_ADMIN)
        admin.set_password("StrongPass!2026")
        admin.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('assignadmin')}")
        assigned = self.client.post(
            "/api/portal/v1/admin/course-instructors/",
            {"course_id": str(self.course.pk), "instructor_id": str(instructor.pk)},
            format="json",
        )
        self.assertEqual(assigned.status_code, 201)
        self.assertTrue(PortalCourseInstructor.objects.filter(course=self.course, instructor=instructor).exists())
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('teacher1')}")
        courses = self.client.get("/api/portal/v1/instructor/courses/")
        self.assertEqual(courses.status_code, 200)
        self.assertEqual([x["id"] for x in courses.data["results"]], [str(self.course.pk)])
        students = self.client.get(f"/api/portal/v1/instructor/courses/{self.course.pk}/students/")
        self.assertEqual(students.status_code, 200)
        self.assertEqual(students.data["results"], [])

    def test_student_cannot_access_instructor_or_assignment_endpoints(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        self.assertEqual(self.client.get("/api/portal/v1/instructor/courses/").status_code, 403)
        self.assertEqual(self.client.get("/api/portal/v1/admin/course-instructors/").status_code, 403)


    def test_admin_cannot_review_own_practice_submission(self):
        admin = PortalIdentity(username="practiceadmin", email="practiceadmin@example.test", role=PortalIdentity.ROLE_ADMIN)
        admin.set_password("StrongPass!2026")
        admin.save()
        submission = PortalPracticeSubmission.objects.create(
            student=admin, lab_key="own-lab", title="Own submission", submission_text="Synthetic"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('practiceadmin')}")
        response = self.client.post(
            f"/api/portal/v1/admin/practice/submissions/{submission.pk}/review/",
            {"status": "approved", "reviewer_notes": "Reviewed"}, format="json",
        )
        self.assertEqual(response.status_code, 403)
        submission.refresh_from_db()
        self.assertEqual(submission.status, "submitted")


    def test_assigned_instructor_can_create_classroom_session_announcement_and_reply(self):
        instructor = PortalIdentity(username="classroomteacher", email="classroomteacher@example.test", role=PortalIdentity.ROLE_INSTRUCTOR)
        instructor.set_password("StrongPass!2026")
        instructor.save()
        PortalCourseInstructor.objects.create(course=self.course, instructor=instructor, assigned_by=self.student)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('classroomteacher')}")
        session = self.client.post(
            f"/api/portal/v1/instructor/courses/{self.course.pk}/classroom/sessions/",
            {
                "title": "Live Python class", "description": "Week one",
                "meeting_url": "https://meet.example.test/class",
                "starts_at": (timezone.now() + timedelta(hours=1)).isoformat(),
                "ends_at": (timezone.now() + timedelta(hours=2)).isoformat(),
            }, format="json",
        )
        self.assertEqual(session.status_code, 201)
        self.assertEqual(session.data["status"], "scheduled")
        self.assertEqual(PortalClassroomSession.objects.get(pk=session.data["id"]).created_by, instructor)
        announcement = self.client.post(
            f"/api/portal/v1/instructor/courses/{self.course.pk}/classroom/announcements/",
            {"title": "Welcome", "body": "Class starts soon."}, format="json",
        )
        self.assertEqual(announcement.status_code, 201)
        self.assertTrue(announcement.data["published"])
        self.assertEqual(PortalClassroomAnnouncement.objects.get(pk=announcement.data["id"]).created_by, instructor)
        reply = self.client.post(
            f"/api/portal/v1/instructor/courses/{self.course.pk}/classroom/teacher-replies/",
            {"message": "Please review lesson one."}, format="json",
        )
        self.assertEqual(reply.status_code, 201)
        self.assertEqual(PortalTeacherReply.objects.get(pk=reply.data["id"]).created_by, instructor)

    def test_instructor_cannot_manage_unassigned_course_or_use_insecure_meeting_link(self):
        instructor = PortalIdentity(username="unassignedteacher", email="unassignedteacher@example.test", role=PortalIdentity.ROLE_INSTRUCTOR)
        instructor.set_password("StrongPass!2026")
        instructor.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('unassignedteacher')}")
        payload = {
            "title": "Class", "meeting_url": "https://meet.example.test",
            "starts_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            "ends_at": (timezone.now() + timedelta(hours=2)).isoformat(),
        }
        denied = self.client.post(
            f"/api/portal/v1/instructor/courses/{self.course.pk}/classroom/sessions/",
            payload, format="json",
        )
        self.assertEqual(denied.status_code, 403)
        PortalCourseInstructor.objects.create(course=self.course, instructor=instructor, assigned_by=self.student)
        payload["meeting_url"] = "http://insecure.example.test"
        invalid = self.client.post(
            f"/api/portal/v1/instructor/courses/{self.course.pk}/classroom/sessions/",
            payload, format="json",
        )
        self.assertEqual(invalid.status_code, 400)


    def test_admin_can_review_valid_bank_payment_submission_and_approve_enrollment(self):
        self.course.fee_amount = Decimal("15000.00")
        self.course.fee_currency = "NGN"
        self.course.save()
        enrollment = PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.PENDING)
        submission = PortalPaymentSubmission.objects.create(
            enrollment=enrollment, student=self.student, course=self.course,
            amount=Decimal("15000.00"), currency="NGN",
            transfer_reference="BANK-REF-001",
            storage_key=f"{self.student.pk}/receipts/receipt-001.pdf",
            content_type="application/pdf", file_name="receipt.pdf",
        )
        admin = PortalIdentity(username="bankreviewadmin", email="bankreviewadmin@example.test", role=PortalIdentity.ROLE_ADMIN)
        admin.set_password("StrongPass!2026")
        admin.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('bankreviewadmin')}")
        queue = self.client.get("/api/portal/v1/admin/payment-submissions/")
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.data["results"][0]["id"], str(submission.pk))
        with patch("student_portal.views.verify_uploaded_receipt", return_value={"ContentLength": 1200, "ContentType": "application/pdf"}):
            response = self.client.post(
                f"/api/portal/v1/admin/payment-submissions/{submission.pk}/review/",
                {"status": "approved", "admin_note": "Verified against bank statement."}, format="json",
            )
        self.assertEqual(response.status_code, 200)
        enrollment.refresh_from_db()
        submission.refresh_from_db()
        self.assertEqual(enrollment.status, PortalEnrollment.APPROVED)
        self.assertEqual(submission.reviewed_by, admin)
        self.assertEqual(submission.status, PortalPaymentSubmission.APPROVED)

    def test_bank_payment_review_rejects_wrong_amount_and_student_cannot_review(self):
        self.course.fee_amount = Decimal("15000.00")
        self.course.fee_currency = "NGN"
        self.course.save()
        enrollment = PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.PENDING)
        submission = PortalPaymentSubmission.objects.create(
            enrollment=enrollment, student=self.student, course=self.course,
            amount=Decimal("10000.00"), currency="NGN",
            storage_key=f"{self.student.pk}/receipts/wrong.pdf",
            content_type="application/pdf",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        denied = self.client.post(
            f"/api/portal/v1/admin/payment-submissions/{submission.pk}/review/",
            {"status": "approved"}, format="json",
        )
        self.assertEqual(denied.status_code, 403)
        admin = PortalIdentity(username="bankreviewadmin2", email="bankreviewadmin2@example.test", role=PortalIdentity.ROLE_ADMIN)
        admin.set_password("StrongPass!2026")
        admin.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('bankreviewadmin2')}")
        mismatch = self.client.post(
            f"/api/portal/v1/admin/payment-submissions/{submission.pk}/review/",
            {"status": "approved"}, format="json",
        )
        self.assertEqual(mismatch.status_code, 400)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, PortalEnrollment.PENDING)

    @patch("student_portal.views.generate_receipt_upload_form")
    def test_student_receipt_upload_is_server_owned_and_requires_finalize(self, upload_mock):
        upload_mock.return_value = {"url": "https://storage.example.test/bucket", "fields": {"key": "opaque"}}
        self.course.fee_amount = Decimal("15000.00")
        self.course.fee_currency = "NGN"
        self.course.save()
        enrollment = PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.PENDING)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        response = self.client.post(
            "/api/portal/v1/student/payment-submissions/upload/",
            {"enrollment_id": str(enrollment.pk), "content_type": "application/pdf", "file_name": "../../receipt.pdf", "transfer_reference": "BANK-REF"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        submission = PortalPaymentSubmission.objects.get(pk=response.data["submission_id"])
        self.assertTrue(submission.storage_key.startswith(f"{self.student.pk}/receipts/"))
        self.assertEqual(submission.file_name, "receipt.pdf")
        self.assertEqual(submission.status, PortalPaymentSubmission.UPLOADING)
        self.assertEqual(submission.amount, Decimal("15000.00"))
        upload_mock.assert_called_once()

    @patch("student_portal.views.verify_uploaded_receipt")
    def test_student_can_finalize_only_their_own_verified_receipt(self, verify_mock):
        self.course.fee_amount = Decimal("15000.00")
        self.course.fee_currency = "NGN"
        self.course.save()
        enrollment = PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.PENDING)
        submission = PortalPaymentSubmission.objects.create(
            enrollment=enrollment, student=self.student, course=self.course,
            amount=Decimal("15000.00"), currency="NGN",
            storage_key=f"{self.student.pk}/receipts/upload-001.pdf",
            content_type="application/pdf", file_name="receipt.pdf",
            status=PortalPaymentSubmission.UPLOADING,
            upload_expires_at=timezone.now() + timedelta(minutes=4),
        )
        verify_mock.return_value = {"ContentLength": 1024, "ContentType": "application/pdf"}
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        response = self.client.post(
            f"/api/portal/v1/student/payment-submissions/{submission.pk}/complete-upload/", {}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        submission.refresh_from_db()
        self.assertEqual(submission.status, PortalPaymentSubmission.PENDING)
        verify_mock.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    def test_receipt_upload_fails_closed_when_private_storage_is_not_configured(self):
        self.course.fee_amount = Decimal("15000.00")
        self.course.save()
        enrollment = PortalEnrollment.objects.create(student=self.student, course=self.course, status=PortalEnrollment.PENDING)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_for('student1')}")
        response = self.client.post(
            "/api/portal/v1/student/payment-submissions/upload/",
            {"enrollment_id": str(enrollment.pk), "content_type": "application/pdf", "file_name": "receipt.pdf"},
            format="json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(PortalPaymentSubmission.objects.exists())
