from django.db import IntegrityError, transaction, models
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import os
import uuid
import requests
from rest_framework import generics, serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from .authentication import PortalJWTAuthentication
from .models import (PortalIdentity, PortalCourse, PortalLesson, PortalEnrollment, PortalLessonProgress, PortalExam, PortalExamQuestion, PortalExamSession, PortalExamAttempt, PortalPayment, PortalCertificate, PortalPracticeSubmission, PortalClassroomSession, PortalClassroomAttendance, PortalClassroomMessage, PortalClassroomAnnouncement, PortalTeacherReply)
from .serializers import PortalRegisterSerializer, PortalTokenSerializer, PortalCourseSerializer, PortalLessonSerializer, PortalEnrollmentCreateSerializer, PortalExamSubmitSerializer, PortalPracticeSubmitSerializer, PortalClassroomMessageSerializer

class PortalRegisterAPIView(generics.CreateAPIView):
    serializer_class = PortalRegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identity = serializer.save()
        return Response({"id": str(identity.pk), "username": identity.username, "email": identity.email}, status=status.HTTP_201_CREATED)


class PortalTokenObtainPairView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PortalTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class PortalMeAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({"id": str(user.pk), "username": user.username, "email": user.email, "role": user.role, "full_name": user.full_name, "phone": user.phone})


class PortalCourseListAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        courses = PortalCourse.objects.filter(is_active=True)
        return Response({"results": PortalCourseSerializer(courses, many=True, context={"request": request}).data})


class PortalCourseDetailAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        if not course:
            raise NotFound("Course not found.")
        return Response(PortalCourseSerializer(course, context={"request": request}).data)


class PortalCourseLessonsAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        enrolled = PortalEnrollment.objects.filter(student=request.user, course_id=course_id, status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED]).exists()
        if not enrolled:
            raise PermissionDenied("An approved enrolment is required to view lessons.")
        lessons = PortalLesson.objects.filter(course_id=course_id, course__is_active=True, is_active=True)
        from .serializers import PortalLessonSerializer
        return Response({"results": PortalLessonSerializer(lessons, many=True).data})


class PortalEnrollmentCreateAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        input_serializer = PortalEnrollmentCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        course_id = input_serializer.validated_data["course_id"]
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        if not course:
            raise NotFound("Active course not found.")
        try:
            with transaction.atomic():
                enrollment = PortalEnrollment.objects.create(student=request.user, course=course, status=PortalEnrollment.PENDING)
        except IntegrityError:
            return Response({"detail": "An enrolment already exists for this course."}, status=status.HTTP_409_CONFLICT)
        return Response({"id": str(enrollment.pk), "course_id": str(course.pk), "status": enrollment.status}, status=status.HTTP_201_CREATED)


class PortalLessonCompleteAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        lesson = PortalLesson.objects.filter(pk=lesson_id, is_active=True, course__is_active=True).first()
        if not lesson:
            raise NotFound("Active lesson not found.")
        allowed = PortalEnrollment.objects.filter(
            student=request.user,
            course=lesson.course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists()
        if not allowed:
            raise PermissionDenied("An approved enrolment is required for this lesson.")
        progress, _ = PortalLessonProgress.objects.get_or_create(
            student=request.user,
            lesson=lesson,
            defaults={"completed_at": timezone.now()},
        )
        return Response({
            "lesson_id": str(lesson.pk),
            "completed_at": progress.completed_at,
        })


class PortalCourseProgressAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        if not course:
            raise NotFound("Active course not found.")
        allowed = PortalEnrollment.objects.filter(
            student=request.user,
            course=course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists()
        if not allowed:
            raise PermissionDenied("An approved enrolment is required for course progress.")
        total = PortalLesson.objects.filter(course=course, is_active=True).count()
        completed = PortalLessonProgress.objects.filter(
            student=request.user,
            lesson__course=course,
            lesson__is_active=True,
        ).count()
        percent = int((completed * 100 / total) + 0.5) if total else 0
        return Response({
            "total_lessons": total,
            "completed_lessons": completed,
            "progress_percent": percent,
        })

class PortalCourseExamsAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        if not course:
            raise NotFound("Active course not found.")
        allowed = PortalEnrollment.objects.filter(
            student=request.user,
            course=course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists()
        if not allowed:
            raise PermissionDenied("An approved enrolment is required to view exams.")
        exams = PortalExam.objects.filter(course=course, is_active=True)
        return Response({"results": [{
            "id": str(exam.pk),
            "title": exam.title,
            "instructions": exam.instructions,
            "duration_minutes": exam.duration_minutes,
            "pass_mark": exam.pass_mark,
            "question_count": exam.questions.count(),
        } for exam in exams]})


class PortalExamStartAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, exam_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        now = timezone.now()
        with transaction.atomic():
            exam = PortalExam.objects.select_for_update().filter(
                pk=exam_id, is_active=True, course__is_active=True
            ).first()
            if not exam:
                raise NotFound("Active exam not found.")
            allowed = PortalEnrollment.objects.filter(
                student=request.user,
                course=exam.course,
                status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
            ).exists()
            if not allowed:
                raise PermissionDenied("An approved enrolment is required to start this exam.")
            question_count = exam.questions.count()
            if question_count < 1 or question_count > 100:
                raise PermissionDenied("This exam is not ready. It must contain between 1 and 100 questions.")

            session = PortalExamSession.objects.select_for_update().filter(
                exam=exam, student=request.user, submitted_at__isnull=True
            ).first()
            if session:
                expires_at = session.started_at + timedelta(minutes=exam.duration_minutes)
                if now < expires_at:
                    return Response({
                        "session_id": str(session.pk),
                        "started_at": session.started_at,
                        "expires_at": expires_at,
                        "resumed": True,
                    })
                PortalExamAttempt.objects.get_or_create(
                    session=session,
                    defaults={
                        "exam": exam,
                        "student": request.user,
                        "answers": {},
                        "score": 0,
                        "passed": False,
                        "started_at": session.started_at,
                        "submitted_at": now,
                    },
                )
                session.submitted_at = now
                session.save(update_fields=["submitted_at"])

            session = PortalExamSession.objects.create(exam=exam, student=request.user)
            expires_at = session.started_at + timedelta(minutes=exam.duration_minutes)
            return Response({
                "session_id": str(session.pk),
                "started_at": session.started_at,
                "expires_at": expires_at,
                "resumed": False,
            }, status=status.HTTP_201_CREATED)


class PortalExamQuestionsAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        session = PortalExamSession.objects.select_related("exam", "exam__course").filter(
            pk=session_id, student=request.user
        ).first()
        if not session:
            raise NotFound("Exam session not found.")
        if session.submitted_at is not None:
            raise PermissionDenied("This exam session is closed.")
        if not session.exam.is_active or not session.exam.course.is_active:
            raise PermissionDenied("This exam is no longer active.")
        allowed = PortalEnrollment.objects.filter(
            student=request.user,
            course=session.exam.course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists()
        if not allowed:
            raise PermissionDenied("An approved enrolment is required.")
        expires_at = session.started_at + timedelta(minutes=session.exam.duration_minutes)
        if timezone.now() >= expires_at:
            return Response({"detail": "The exam time has expired."}, status=status.HTTP_410_GONE)

        questions = session.exam.questions.all()
        payload = []
        for question in questions:
            if not isinstance(question.options, list) or len(question.options) != 4:
                raise PermissionDenied("This exam contains a question with invalid options.")
            payload.append({
                "id": str(question.pk),
                "question_text": question.question_text,
                "options": question.options,
                "sort_order": question.sort_order,
            })
        return Response({"session_id": str(session.pk), "expires_at": expires_at, "results": payload})


class PortalExamSubmitAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        serializer = PortalExamSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submitted_answers = serializer.validated_data["answers"]

        with transaction.atomic():
            session = PortalExamSession.objects.select_for_update().select_related(
                "exam", "exam__course"
            ).filter(pk=session_id, student=request.user).first()
            if not session:
                raise NotFound("Exam session not found.")
            existing = PortalExamAttempt.objects.filter(session=session).first()
            if existing:
                return Response({
                    "attempt_id": str(existing.pk),
                    "score": existing.score,
                    "passed": existing.passed,
                    "submitted_at": existing.submitted_at,
                })
            if session.submitted_at is not None:
                raise PermissionDenied("This exam session is already closed.")
            allowed = PortalEnrollment.objects.filter(
                student=request.user,
                course=session.exam.course,
                status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
            ).exists()
            if not allowed:
                raise PermissionDenied("An approved enrolment is required.")
            now = timezone.now()
            expired = now >= session.started_at + timedelta(minutes=session.exam.duration_minutes)
            questions = list(session.exam.questions.all())
            if not expired:
                expected_ids = {str(question.pk) for question in questions}
                if len(questions) < 1 or len(questions) > 100 or set(submitted_answers) != expected_ids:
                    raise serializers.ValidationError({
                        "answers": "Submit exactly one answer for every question in this exam."
                    })
                correct = sum(
                    1 for question in questions
                    if submitted_answers[str(question.pk)] == question.correct_option
                )
                score = int((correct * 100 / len(questions)) + 0.5)
                answers_to_store = submitted_answers
            else:
                score = 0
                answers_to_store = {}
            passed = (not expired) and score >= session.exam.pass_mark
            attempt = PortalExamAttempt.objects.create(
                session=session,
                exam=session.exam,
                student=request.user,
                answers=answers_to_store,
                score=score,
                passed=passed,
                started_at=session.started_at,
                submitted_at=now,
            )
            session.submitted_at = now
            session.save(update_fields=["submitted_at"])
            return Response({
                "attempt_id": str(attempt.pk),
                "score": attempt.score,
                "passed": attempt.passed,
                "submitted_at": attempt.submitted_at,
            }, status=status.HTTP_201_CREATED)

class PortalPaymentInitializeAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, enrollment_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        secret = os.environ.get("PAYSTACK_SECRET_KEY", "").strip()
        expected_domain = os.environ.get("PAYSTACK_EXPECTED_DOMAIN", "").strip().lower()
        if not secret or expected_domain not in ("test", "live"):
            return Response({"detail": "Online payment is not configured yet."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if (expected_domain == "test" and not secret.startswith("sk_test_")) or (
            expected_domain == "live" and not secret.startswith("sk_live_")
        ):
            return Response({"detail": "Payment gateway environment configuration is invalid."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        with transaction.atomic():
            enrollment = PortalEnrollment.objects.select_for_update().select_related("course").filter(
                pk=enrollment_id,
                student=request.user,
                status=PortalEnrollment.PENDING,
                course__is_active=True,
            ).first()
            if not enrollment:
                raise NotFound("A pending enrolment for an active course was not found.")
            course = enrollment.course
            if course.fee_currency != "NGN" or course.fee_amount <= 0:
                raise serializers.ValidationError("This course is not configured for NGN online payment.")
            amount_kobo = int((course.fee_amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            payment = PortalPayment.objects.filter(
                enrollment=enrollment, status=PortalPayment.PENDING
            ).first()
            if payment and (payment.amount_kobo != amount_kobo or payment.currency != "NGN"):
                payment.status = PortalPayment.ABANDONED
                payment.save(update_fields=["status"])
                payment = None
            if payment is None:
                payment = PortalPayment.objects.create(
                    enrollment=enrollment,
                    student=request.user,
                    reference=f"YSCMT_{uuid.uuid4().hex.upper()}",
                    amount_kobo=amount_kobo,
                    currency="NGN",
                    status=PortalPayment.PENDING,
                )
            if payment.authorization_url:
                return Response({
                    "reference": payment.reference,
                    "authorization_url": payment.authorization_url,
                    "amount_kobo": payment.amount_kobo,
                    "currency": payment.currency,
                })

        try:
            response = requests.post(
                "https://api.paystack.co/transaction/initialize",
                headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
                json={
                    "email": request.user.email,
                    "amount": payment.amount_kobo,
                    "currency": payment.currency,
                    "reference": payment.reference,
                    "metadata": {
                        "student_id": str(request.user.pk),
                        "enrollment_id": str(enrollment.pk),
                        "provider": "YSCMT Enterprise",
                    },
                },
                timeout=15,
            )
            payload = response.json()
        except (requests.RequestException, ValueError):
            return Response({"detail": "Paystack is temporarily unavailable. Please retry shortly."}, status=status.HTTP_502_BAD_GATEWAY)

        data = payload.get("data") if isinstance(payload, dict) else None
        if response.status_code != 200 or not isinstance(data, dict) or payload.get("status") is not True:
            return Response({"detail": "Paystack could not initialize this payment."}, status=status.HTTP_502_BAD_GATEWAY)
        authorization_url = data.get("authorization_url", "")
        returned_reference = data.get("reference", "")
        from urllib.parse import urlparse
        parsed_url = urlparse(authorization_url)
        if (
            returned_reference != payment.reference
            or parsed_url.scheme != "https"
            or parsed_url.hostname != "checkout.paystack.com"
        ):
            return Response({"detail": "Paystack returned invalid checkout details."}, status=status.HTTP_502_BAD_GATEWAY)

        PortalPayment.objects.filter(pk=payment.pk, status=PortalPayment.PENDING).update(
            authorization_url=authorization_url
        )
        return Response({
            "reference": payment.reference,
            "authorization_url": authorization_url,
            "amount_kobo": payment.amount_kobo,
            "currency": payment.currency,
        }, status=status.HTTP_201_CREATED)


class PortalPaymentVerifyAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, reference):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        secret = os.environ.get("PAYSTACK_SECRET_KEY", "").strip()
        expected_domain = os.environ.get("PAYSTACK_EXPECTED_DOMAIN", "").strip().lower()
        if not secret or expected_domain not in ("test", "live"):
            return Response({"detail": "Online payment verification is not configured yet."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if (expected_domain == "test" and not secret.startswith("sk_test_")) or (
            expected_domain == "live" and not secret.startswith("sk_live_")
        ):
            return Response({"detail": "Payment gateway environment configuration is invalid."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        payment = PortalPayment.objects.filter(reference=reference, student=request.user).select_related("enrollment").first()
        if not payment:
            raise NotFound("Payment reference not found for this account.")
        if payment.status == PortalPayment.SUCCESS:
            return Response({
                "reference": payment.reference,
                "status": payment.status,
                "enrollment_status": payment.enrollment.status,
                "verified_at": payment.verified_at,
            })
        if payment.status != PortalPayment.PENDING:
            raise PermissionDenied("This payment is no longer pending.")

        try:
            response = requests.get(
                f"https://api.paystack.co/transaction/verify/{payment.reference}",
                headers={"Authorization": f"Bearer {secret}"},
                timeout=15,
            )
            payload = response.json()
        except (requests.RequestException, ValueError):
            return Response({"detail": "Paystack verification is temporarily unavailable."}, status=status.HTTP_502_BAD_GATEWAY)

        data = payload.get("data") if isinstance(payload, dict) else None
        if response.status_code != 200 or not isinstance(data, dict) or payload.get("status") is not True:
            return Response({"detail": "Paystack could not verify this payment."}, status=status.HTTP_502_BAD_GATEWAY)
        if data.get("status") != "success":
            return Response({"reference": payment.reference, "status": "pending", "confirmed": False}, status=status.HTTP_202_ACCEPTED)

        if (
            data.get("reference") != payment.reference
            or data.get("amount") != payment.amount_kobo
            or data.get("currency") != payment.currency
            or data.get("domain") != expected_domain
        ):
            return Response({"detail": "Verified Paystack details do not match this payment."}, status=status.HTTP_400_BAD_REQUEST)

        gateway_response = {
            "status": data.get("status"),
            "reference": data.get("reference"),
            "amount": data.get("amount"),
            "currency": data.get("currency"),
            "domain": data.get("domain"),
            "paid_at": data.get("paid_at"),
            "channel": data.get("channel"),
            "transaction_id": data.get("id"),
        }
        with transaction.atomic():
            payment = PortalPayment.objects.select_for_update().select_related("enrollment", "enrollment__course").get(pk=payment.pk)
            if payment.status == PortalPayment.SUCCESS:
                return Response({
                    "reference": payment.reference,
                    "status": payment.status,
                    "enrollment_status": payment.enrollment.status,
                    "verified_at": payment.verified_at,
                })
            enrollment = PortalEnrollment.objects.select_for_update().get(pk=payment.enrollment_id)
            current_amount = int((enrollment.course.fee_amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            if (
                enrollment.student_id != request.user.pk
                or current_amount != payment.amount_kobo
                or enrollment.course.fee_currency != payment.currency
                or enrollment.status not in [PortalEnrollment.PENDING, PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED]
            ):
                return Response({"detail": "The payment is verified, but the enrolment needs administrator reconciliation."}, status=status.HTTP_409_CONFLICT)
            payment.status = PortalPayment.SUCCESS
            payment.gateway_response = gateway_response
            payment.verified_at = timezone.now()
            payment.save(update_fields=["status", "gateway_response", "verified_at"])
            if enrollment.status == PortalEnrollment.PENDING:
                enrollment.status = PortalEnrollment.APPROVED
                enrollment.save(update_fields=["status", "updated_at"])

        return Response({
            "reference": payment.reference,
            "status": payment.status,
            "enrollment_status": enrollment.status,
            "verified_at": payment.verified_at,
        })

class PortalCertificateRequestAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        if not course:
            raise NotFound("Active course not found.")
        allowed = PortalEnrollment.objects.filter(
            student=request.user,
            course=course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists()
        if not allowed:
            raise PermissionDenied("An approved enrolment is required.")
        total_lessons = PortalLesson.objects.filter(course=course, is_active=True).count()
        completed_lessons = PortalLessonProgress.objects.filter(
            student=request.user,
            lesson__course=course,
            lesson__is_active=True,
            completed_at__isnull=False,
        ).count()
        if total_lessons == 0 or completed_lessons != total_lessons:
            raise serializers.ValidationError("Complete every active lesson before requesting a certificate.")
        passed_exam = PortalExamAttempt.objects.filter(
            student=request.user, exam__course=course, passed=True
        ).exists()
        if not passed_exam:
            raise serializers.ValidationError("Pass at least one course exam before requesting a certificate.")

        certificate, _ = PortalCertificate.objects.get_or_create(
            student=request.user,
            course=course,
            defaults={
                "certificate_code": f"YSCMT-{uuid.uuid4().hex[:12].upper()}",
                "student_name": request.user.full_name.strip() or "YSCMT Student",
                "course_title": course.title,
            },
        )
        return Response({
            "id": str(certificate.pk),
            "certificate_code": certificate.certificate_code,
            "student_name": certificate.student_name,
            "course_title": certificate.course_title,
            "issued_at": certificate.issued_at,
        }, status=status.HTTP_201_CREATED)


class PortalCertificateListAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        certificates = PortalCertificate.objects.filter(student=request.user)
        return Response({"results": [{
            "id": str(item.pk),
            "certificate_code": item.certificate_code,
            "student_name": item.student_name,
            "course_title": item.course_title,
            "issued_at": item.issued_at,
        } for item in certificates]})


class PortalCertificateVerifyAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, certificate_code):
        certificate = PortalCertificate.objects.filter(
            certificate_code=certificate_code.strip().upper()
        ).first()
        if not certificate:
            return Response({"valid": False}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "valid": True,
            "certificate_code": certificate.certificate_code,
            "student_name": certificate.student_name,
            "course_title": certificate.course_title,
            "issued_at": certificate.issued_at,
        })

class PortalClassroomSessionListAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        if not course:
            raise NotFound("Active course not found.")
        allowed = PortalEnrollment.objects.filter(
            student=request.user, course=course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists()
        if not allowed:
            raise PermissionDenied("An approved enrolment is required to view classroom sessions.")
        sessions = PortalClassroomSession.objects.filter(
            course=course
        ).exclude(status="cancelled").order_by("-starts_at")[:100]
        return Response({"results": [{
            "id": str(item.pk),
            "title": item.title,
            "description": item.description,
            "meeting_url": item.meeting_url,
            "starts_at": item.starts_at,
            "ends_at": item.ends_at,
            "status": item.status,
            "joined_at": PortalClassroomAttendance.objects.filter(
                session=item, student=request.user
            ).values_list("joined_at", flat=True).first(),
        } for item in sessions]})


class PortalClassroomJoinAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        session = PortalClassroomSession.objects.select_related("course").filter(pk=session_id).first()
        if not session:
            raise NotFound("Classroom session not found.")
        allowed = PortalEnrollment.objects.filter(
            student=request.user, course=session.course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists()
        now = timezone.now()
        if (
            not allowed
            or session.status not in ["scheduled", "live"]
            or now < session.starts_at - timedelta(minutes=15)
            or now > session.ends_at
        ):
            raise PermissionDenied("This classroom session is not open to this student.")
        attendance, _ = PortalClassroomAttendance.objects.get_or_create(
            session=session, student=request.user
        )
        return Response({
            "attendance_id": str(attendance.pk),
            "joined_at": attendance.joined_at,
        })


class PortalClassroomMessageAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _course(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        if not course:
            raise NotFound("Active course not found.")
        if not PortalEnrollment.objects.filter(
            student=request.user, course=course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists():
            raise PermissionDenied("An approved enrolment is required for classroom messages.")
        return course

    def get(self, request, course_id):
        course = self._course(request, course_id)
        messages = list(PortalClassroomMessage.objects.filter(course=course).order_by("-created_at")[:100])
        messages.reverse()
        return Response({"results": [{
            "id": str(item.pk),
            "author_role": item.author_role,
            "message": item.message,
            "created_at": item.created_at,
        } for item in messages]})

    def post(self, request, course_id):
        course = self._course(request, course_id)
        serializer = PortalClassroomMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = PortalClassroomMessage.objects.create(
            course=course, student=request.user, author_role="student",
            message=serializer.validated_data["message"].strip(),
        )
        return Response({
            "id": str(item.pk), "message": item.message, "created_at": item.created_at,
        }, status=status.HTTP_201_CREATED)


class PortalClassroomAnnouncementsAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        if not course:
            raise NotFound("Active course not found.")
        enrolled = PortalEnrollment.objects.filter(
            student=request.user, course=course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists()
        query = PortalClassroomAnnouncement.objects.filter(published=True).filter(
            models.Q(course__isnull=True) | models.Q(course=course)
        )
        if not enrolled:
            query = query.filter(course__isnull=True)
        return Response({"results": [{
            "id": str(item.pk),
            "course_id": str(item.course_id) if item.course_id else None,
            "title": item.title,
            "body": item.body,
            "created_at": item.created_at,
        } for item in query[:100]]})


class PortalTeacherRepliesAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        if not course:
            raise NotFound("Active course not found.")
        allowed = PortalEnrollment.objects.filter(
            student=request.user, course=course,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists()
        if not allowed:
            raise PermissionDenied("An approved enrolment is required to view teacher replies.")
        replies = PortalTeacherReply.objects.filter(course=course)[:100]
        return Response({"results": [{
            "id": str(item.pk), "message": item.message, "created_at": item.created_at,
        } for item in replies]})


class PortalPracticeSubmissionAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        submissions = PortalPracticeSubmission.objects.filter(student=request.user)[:100]
        return Response({"results": [{
            "id": str(item.pk),
            "lab_key": item.lab_key,
            "title": item.title,
            "submission_text": item.submission_text,
            "project_url": item.project_url,
            "status": item.status,
            "reviewer_notes": item.reviewer_notes,
            "submitted_at": item.submitted_at,
            "reviewed_at": item.reviewed_at,
        } for item in submissions]})

    def post(self, request):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        if not PortalEnrollment.objects.filter(
            student=request.user,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
        ).exists():
            raise PermissionDenied("An approved course enrolment is required to submit practice work.")
        serializer = PortalPracticeSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = PortalPracticeSubmission.objects.create(
            student=request.user,
            lab_key=serializer.validated_data["lab_key"].strip(),
            title=serializer.validated_data["title"].strip(),
            submission_text=serializer.validated_data.get("submission_text", ""),
            project_url=serializer.validated_data.get("project_url", ""),
        )
        return Response({
            "id": str(item.pk),
            "status": item.status,
            "submitted_at": item.submitted_at,
        }, status=status.HTTP_201_CREATED)
