from django.db import IntegrityError, transaction, models
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import os
import uuid
import re
from types import SimpleNamespace
import hashlib
import secrets
from urllib.parse import urlencodequests
import re
from rest_framework import generics, serializers, status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.password_validation import validate_password
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from .authentication import PortalJWTAuthentication
from .storage import generate_receipt_upload_form, verify_uploaded_receipt, generate_receipt_download_url, ReceiptStorageError
from .models import (PortalIdentity, PortalPasswordResetToken, PortalCourse, PortalCourseInstructor, PortalLesson, PortalEnrollment, PortalLessonProgress, PortalExam, PortalExamQuestion, PortalExamSession, PortalExamAttempt, PortalPayment, PortalPaymentSubmission, PortalCertificate, PortalPracticeSubmission, PortalClassroomSession, PortalClassroomAttendance, PortalClassroomMessage, PortalClassroomAnnouncement, PortalTeacherReply, PortalSiteSetting, PortalAuditLog)
from .serializers import PortalRegisterSerializer, PortalTokenSerializer, PortalCourseSerializer, PortalLessonSerializer, PortalEnrollmentCreateSerializer, PortalExamSubmitSerializer, PortalPracticeSubmitSerializer, PortalClassroomMessageSerializer

class PortalStorageUnavailable(APIException):
    status_code = 503
    default_detail = "Private receipt storage is not configured or is temporarily unavailable."
    default_code = "private_storage_unavailable"


class PortalEmailUnavailable(APIException):
    status_code = 503
    default_detail = "Password reset email is not configured or is temporarily unavailable."
    default_code = "password_reset_email_unavailable"


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


class PortalPasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = serializers.EmailField().run_validation(request.data.get("email"))
        if not settings.EMAIL_HOST:
            raise PortalEmailUnavailable()
        identity = PortalIdentity.objects.filter(email__iexact=email, is_active=True).first()
        if not identity:
            return Response({"detail": "If the account exists, a reset link has been sent."})
        recent = PortalPasswordResetToken.objects.filter(
            identity=identity, created_at__gte=timezone.now() - timedelta(seconds=60),
            used_at__isnull=True,
        ).exists()
        if recent:
            return Response({"detail": "If the account exists, a reset link has been sent."})
        now = timezone.now()
        PortalPasswordResetToken.objects.filter(
            identity=identity, used_at__isnull=True
        ).update(used_at=now)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        PortalPasswordResetToken.objects.create(
            identity=identity, token_hash=token_hash,
            expires_at=now + timedelta(minutes=30),
        )
        reset_url = settings.FRONTEND_URL + "/reset-password?" + urlencode({"token": raw_token})
        message = (
            f"Hello {identity.full_name or identity.username},\n\n"
            f"Use this secure link to set your YSCMT Student Portal password. "
            f"It expires in 30 minutes and can be used once:\n{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        )
        try:
            sent = send_mail(
                subject="Reset your YSCMT Student Portal password",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[identity.email],
                fail_silently=False,
            )
            if sent != 1:
                raise RuntimeError("Password reset email was not accepted by the email backend.")
        except Exception as exc:
            PortalPasswordResetToken.objects.filter(token_hash=token_hash).update(used_at=timezone.now())
            raise PortalEmailUnavailable() from exc
        return Response({"detail": "If the account exists, a reset link has been sent."})


class PortalPasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_token = request.data.get("token")
        raw_password = request.data.get("new_password")
        if not isinstance(raw_token, str) or len(raw_token) < 20 or len(raw_token) > 200:
            raise serializers.ValidationError({"token": "A valid reset token is required."})
        if not isinstance(raw_password, str):
            raise serializers.ValidationError({"new_password": "A new password is required."})
        validate_password(raw_password)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        with transaction.atomic():
            token = PortalPasswordResetToken.objects.select_for_update().select_related("identity").filter(
                token_hash=token_hash, used_at__isnull=True, expires_at__gt=timezone.now(),
                identity__is_active=True,
            ).first()
            if not token:
                raise serializers.ValidationError({"token": "This reset link is invalid or expired."})
            identity = token.identity
            identity.set_password(raw_password)
            identity.must_reset_password = False
            if identity.email_verified_at is None:
                identity.email_verified_at = timezone.now()
            identity.save(update_fields=["password", "must_reset_password", "email_verified_at", "updated_at"])
            now = timezone.now()
            PortalPasswordResetToken.objects.filter(identity=identity, used_at__isnull=True).update(used_at=now)
        return Response({"detail": "Password updated. You can now sign in."})


class PortalMeAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": str(user.pk), "username": user.username, "email": user.email,
            "role": user.role, "full_name": user.full_name, "phone": user.phone,
            "avatar_url": user.avatar_url,
        })

    def patch(self, request):
        user = request.user
        full_name = request.data.get("full_name", user.full_name)
        phone = request.data.get("phone", user.phone)
        avatar_url = request.data.get("avatar_url", user.avatar_url)
        if not isinstance(full_name, str) or len(full_name) > 200:
            raise serializers.ValidationError({"full_name": "Name must be text up to 200 characters."})
        if not isinstance(phone, str) or len(phone) > 40:
            raise serializers.ValidationError({"phone": "Phone must be text up to 40 characters."})
        if avatar_url is not None and (not isinstance(avatar_url, str) or (avatar_url and not avatar_url.startswith("https://")) or len(avatar_url) > 2048):
            raise serializers.ValidationError({"avatar_url": "Avatar URL must be an HTTPS URL up to 2048 characters."})
        user.full_name = full_name.strip()
        user.phone = phone.strip()
        user.avatar_url = avatar_url.strip() if isinstance(avatar_url, str) and avatar_url.strip() else None
        user.save(update_fields=["full_name", "phone", "avatar_url", "updated_at"])
        return Response({
            "id": str(user.pk), "username": user.username, "email": user.email,
            "role": user.role, "full_name": user.full_name, "phone": user.phone,
            "avatar_url": user.avatar_url,
        })


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

class PortalStudentClassroomAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _enrollments(self, request):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        return list(PortalEnrollment.objects.filter(
            student=request.user,
            status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED],
            course__is_active=True,
        ).select_related("course"))

    def get(self, request):
        enrollments = self._enrollments(request)
        course_ids = [item.course_id for item in enrollments]
        sessions = PortalClassroomSession.objects.none()
        announcements = PortalClassroomAnnouncement.objects.filter(published=True, course__isnull=True)
        messages = []
        if course_ids:
            sessions = PortalClassroomSession.objects.filter(
                course_id__in=course_ids,
            ).exclude(status="cancelled").select_related("course").order_by("-starts_at")[:100]
            announcements = PortalClassroomAnnouncement.objects.filter(
                published=True,
            ).filter(models.Q(course__isnull=True) | models.Q(course_id__in=course_ids)).order_by("-created_at")[:100]
            student_messages = PortalClassroomMessage.objects.filter(
                course_id__in=course_ids,
            ).order_by("-created_at")[:100]
            teacher_replies = PortalTeacherReply.objects.filter(
                course_id__in=course_ids,
            ).order_by("-created_at")[:100]
            messages = [{
                "id": str(item.pk), "course_id": str(item.course_id),
                "author_role": item.author_role, "message": item.message,
                "created_at": item.created_at,
            } for item in student_messages]
            messages += [{
                "id": str(item.pk), "course_id": str(item.course_id),
                "author_role": "teacher", "message": item.message,
                "created_at": item.created_at,
            } for item in teacher_replies]
            messages.sort(key=lambda item: item["created_at"], reverse=True)
        return Response({
            "courses": [{"course_id": str(item.course_id), "title": item.course.title} for item in enrollments],
            "sessions": [{
                "id": str(item.pk), "course_id": str(item.course_id),
                "course_title": item.course.title, "title": item.title,
                "description": item.description, "meeting_url": item.meeting_url,
                "starts_at": item.starts_at, "ends_at": item.ends_at,
                "status": item.status,
                "attended": PortalClassroomAttendance.objects.filter(session=item, student=request.user).exists(),
            } for item in sessions],
            "announcements": [{
                "id": str(item.pk), "course_id": str(item.course_id) if item.course_id else None,
                "title": item.title, "body": item.body, "created_at": item.created_at,
            } for item in announcements],
            "messages": messages[:100],
        })

    def post(self, request):
        enrollments = self._enrollments(request)
        course_ids = {item.course_id for item in enrollments}
        action = request.data.get("action")
        if action == "message":
            course_id = request.data.get("course_id")
            if course_id not in {str(item) for item in course_ids}:
                raise serializers.ValidationError({"course_id": "Choose one of your approved courses."})
            message = request.data.get("message")
            if not isinstance(message, str) or not message.strip() or len(message) > 3000:
                raise serializers.ValidationError({"message": "Message must contain 1 to 3000 characters."})
            item = PortalClassroomMessage.objects.create(
                course_id=course_id, student=request.user,
                author_role="student", message=message.strip(),
            )
            return Response({"message": {
                "id": str(item.pk), "course_id": str(item.course_id),
                "author_role": "student", "message": item.message,
                "created_at": item.created_at,
            }}, status=status.HTTP_201_CREATED)
        if action == "join":
            session_id = request.data.get("session_id")
            item = PortalClassroomSession.objects.filter(pk=session_id).first()
            if not item:
                raise NotFound("Class session not found.")
            if item.course_id not in course_ids:
                raise PermissionDenied("This class is not part of your approved enrolments.")
            if item.status in ["cancelled", "completed"]:
                return Response({"detail": "This class is no longer available."}, status=status.HTTP_409_CONFLICT)
            PortalClassroomAttendance.objects.get_or_create(session=item, student=request.user)
            return Response({"meeting_url": item.meeting_url, "session_id": str(item.pk)})
        raise serializers.ValidationError({"action": "Unknown classroom action."})


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
        results = [{
            "id": str(item.pk),
            "lab_key": item.lab_key,
            "title": item.title,
            "submission_text": item.submission_text,
            "project_url": item.project_url,
            "status": item.status,
            "reviewer_notes": item.reviewer_notes,
            "submitted_at": item.submitted_at,
            "reviewed_at": item.reviewed_at,
        } for item in submissions]
        return Response({"submissions": results, "results": results})

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



class PortalInstructorClassroomSessionAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_INSTRUCTOR:
            raise PermissionDenied("Instructor access only.")
        course = PortalCourse.objects.filter(
            pk=course_id, is_active=True,
            instructor_assignments__instructor=request.user,
        ).first()
        if not course:
            raise PermissionDenied("This active course is not assigned to your instructor account.")
        title = request.data.get("title")
        description = request.data.get("description", "")
        meeting_url = request.data.get("meeting_url")
        if not isinstance(title, str) or not title.strip() or len(title) > 220:
            raise serializers.ValidationError({"title": "Title is required and must be at most 220 characters."})
        if not isinstance(description, str) or len(description) > 5000:
            raise serializers.ValidationError({"description": "Description must be text up to 5000 characters."})
        if not isinstance(meeting_url, str) or not meeting_url.startswith("https://"):
            raise serializers.ValidationError({"meeting_url": "Meeting links must use HTTPS."})
        try:
            starts_at = serializers.DateTimeField().run_validation(request.data.get("starts_at"))
            ends_at = serializers.DateTimeField().run_validation(request.data.get("ends_at"))
        except serializers.ValidationError:
            raise serializers.ValidationError({"starts_at": "Provide valid starts_at and ends_at timestamps."})
        if ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "The session must end after it starts."})
        item = PortalClassroomSession.objects.create(
            course=course, title=title.strip(), description=description.strip(),
            meeting_url=meeting_url, starts_at=starts_at, ends_at=ends_at,
            status="scheduled", created_by=request.user, created_by_handle=request.user.username,
        )
        PortalAuditLog.objects.create(
            actor=request.user, action="classroom.session_created",
            target_type="classroom_session", target_id=str(item.pk),
            metadata={"course_id": str(course.pk)},
        )
        return Response({
            "id": str(item.pk), "course_id": str(course.pk), "title": item.title,
            "meeting_url": item.meeting_url, "starts_at": item.starts_at,
            "ends_at": item.ends_at, "status": item.status,
        }, status=status.HTTP_201_CREATED)


class PortalInstructorAnnouncementAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_INSTRUCTOR:
            raise PermissionDenied("Instructor access only.")
        course = PortalCourse.objects.filter(
            pk=course_id, is_active=True,
            instructor_assignments__instructor=request.user,
        ).first()
        if not course:
            raise PermissionDenied("This active course is not assigned to your instructor account.")
        title, body = request.data.get("title"), request.data.get("body")
        if not isinstance(title, str) or not title.strip() or len(title) > 220:
            raise serializers.ValidationError({"title": "Title is required and must be at most 220 characters."})
        if not isinstance(body, str) or not body.strip() or len(body) > 10000:
            raise serializers.ValidationError({"body": "Announcement text is required and must be at most 10000 characters."})
        item = PortalClassroomAnnouncement.objects.create(
            course=course, title=title.strip(), body=body.strip(), published=True, created_by=request.user, created_by_handle=request.user.username,
        )
        PortalAuditLog.objects.create(
            actor=request.user, action="classroom.announcement_published",
            target_type="classroom_announcement", target_id=str(item.pk),
            metadata={"course_id": str(course.pk)},
        )
        return Response({
            "id": str(item.pk), "course_id": str(course.pk),
            "title": item.title, "body": item.body, "published": item.published,
        }, status=status.HTTP_201_CREATED)


class PortalInstructorTeacherReplyAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_INSTRUCTOR:
            raise PermissionDenied("Instructor access only.")
        course = PortalCourse.objects.filter(
            pk=course_id, is_active=True,
            instructor_assignments__instructor=request.user,
        ).first()
        if not course:
            raise PermissionDenied("This active course is not assigned to your instructor account.")
        message = request.data.get("message")
        if not isinstance(message, str) or not message.strip() or len(message) > 3000:
            raise serializers.ValidationError({"message": "Reply must contain 1 to 3000 characters."})
        item = PortalTeacherReply.objects.create(
            course=course, created_by=request.user, created_by_handle=request.user.username, message=message.strip(),
        )
        PortalAuditLog.objects.create(
            actor=request.user, action="classroom.teacher_reply_created",
            target_type="teacher_reply", target_id=str(item.pk),
            metadata={"course_id": str(course.pk)},
        )
        return Response({
            "id": str(item.pk), "course_id": str(course.pk),
            "message": item.message, "created_at": item.created_at,
        }, status=status.HTTP_201_CREATED)


class PortalAdminEnrollmentAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        state = request.query_params.get("status", PortalEnrollment.PENDING)
        if state not in dict(PortalEnrollment.STATUS_CHOICES):
            raise serializers.ValidationError({"status": "Invalid enrolment status."})
        records = PortalEnrollment.objects.filter(status=state).select_related("student", "course")[:200]
        return Response({"results": [{
            "id": str(item.pk),
            "student_id": str(item.student_id),
            "student_name": item.student.full_name or item.student.username,
            "student_email": item.student.email,
            "course_id": str(item.course_id),
            "course_title": item.course.title,
            "status": item.status,
            "created_at": item.created_at,
        } for item in records]})

    def post(self, request, enrollment_id):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        new_status = request.data.get("status")
        note = request.data.get("note", "")
        if new_status not in [PortalEnrollment.APPROVED, PortalEnrollment.REJECTED, PortalEnrollment.COMPLETED]:
            raise serializers.ValidationError({"status": "Choose approved, rejected or completed."})
        if not isinstance(note, str) or len(note) > 2000:
            raise serializers.ValidationError({"note": "Note must be text up to 2000 characters."})
        with transaction.atomic():
            enrollment = PortalEnrollment.objects.select_for_update().select_related("student", "course").filter(pk=enrollment_id).first()
            if not enrollment:
                raise NotFound("Enrolment not found.")
            previous = enrollment.status
            if enrollment.student_id == request.user.pk:
                raise PermissionDenied("An administrator cannot review their own enrolment.")
            if previous == PortalEnrollment.COMPLETED and new_status != PortalEnrollment.COMPLETED:
                raise serializers.ValidationError({"status": "A completed enrolment cannot be downgraded."})
            if previous in [PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED] and new_status == PortalEnrollment.REJECTED:
                raise serializers.ValidationError({"status": "An approved or completed enrolment cannot be rejected here."})
            if new_status == PortalEnrollment.COMPLETED:
                active_lessons = PortalLesson.objects.filter(course=enrollment.course, is_active=True)
                total = active_lessons.count()
                completed = PortalLessonProgress.objects.filter(
                    student=enrollment.student, lesson__in=active_lessons,
                    completed_at__isnull=False,
                ).count()
                passed_exam = PortalExamAttempt.objects.filter(
                    student=enrollment.student, exam__course=enrollment.course, passed=True,
                ).exists()
                if total == 0 or completed != total or not passed_exam:
                    raise serializers.ValidationError({
                        "status": "Student must complete all active lessons and pass at least one course exam before completion."
                    })
            enrollment.status = new_status
            enrollment.save(update_fields=["status", "updated_at"])
            PortalAuditLog.objects.create(
                actor=request.user, action="enrollment.status_changed",
                target_type="enrollment", target_id=str(enrollment.pk),
                metadata={"from": previous, "to": new_status, "note": note.strip(), "student_id": str(enrollment.student_id), "course_id": str(enrollment.course_id)},
            )
        return Response({"id": str(enrollment.pk), "status": enrollment.status})



class PortalBankReceiptUploadAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Only students can upload bank payment receipts.")
        enrollment_id = request.data.get("enrollment_id")
        content_type = request.data.get("content_type")
        file_name = request.data.get("file_name")
        transfer_reference = request.data.get("transfer_reference", "")
        if not isinstance(transfer_reference, str) or len(transfer_reference) > 120:
            raise serializers.ValidationError({"transfer_reference": "Reference must be text up to 120 characters."})
        if not isinstance(file_name, str) or not file_name.strip() or len(file_name) > 255:
            raise serializers.ValidationError({"file_name": "A filename up to 255 characters is required."})
        safe_name = file_name.replace("\\", "/").split("/")[-1].strip()
        safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", safe_name)[:180]
        extension = safe_name.lower().rsplit(".", 1)[-1] if "." in safe_name else ""
        allowed = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
        if extension not in allowed or content_type != allowed[extension]:
            raise serializers.ValidationError({"content_type": "Only matching PDF, JPG, JPEG or PNG receipts are accepted."})
        enrollment = PortalEnrollment.objects.select_related("course").filter(
            pk=enrollment_id, student=request.user, status=PortalEnrollment.PENDING,
            course__is_active=True,
        ).first()
        if not enrollment:
            raise NotFound("Pending enrolment not found.")
        if enrollment.course.fee_amount <= 0:
            raise serializers.ValidationError({"enrollment_id": "This course does not require a bank payment."})
        if PortalPaymentSubmission.objects.filter(
            enrollment=enrollment,
            status__in=[PortalPaymentSubmission.UPLOADING, PortalPaymentSubmission.PENDING],
        ).exists():
            raise serializers.ValidationError({"enrollment_id": "A bank receipt is already being uploaded or awaiting review."})
        storage_key = f"{request.user.pk}/receipts/{uuid.uuid4().hex}.{extension}"
        expires_at = timezone.now() + timedelta(minutes=5)
        try:
            upload = generate_receipt_upload_form(
                storage_key=storage_key, owner_id=str(request.user.pk),
                content_type=content_type, max_bytes=5 * 1024 * 1024,
                expires_seconds=300,
            )
        except ReceiptStorageError:
            raise PortalStorageUnavailable()
        submission = PortalPaymentSubmission.objects.create(
            enrollment=enrollment, student=request.user, course=enrollment.course,
            amount=enrollment.course.fee_amount, currency=enrollment.course.fee_currency,
            transfer_reference=transfer_reference.strip(), storage_key=storage_key,
            content_type=content_type, file_name=safe_name,
            status=PortalPaymentSubmission.UPLOADING, upload_expires_at=expires_at,
        )
        return Response({
            "submission_id": str(submission.pk),
            "upload_method": "POST",
            "upload_url": upload["url"],
            "upload_fields": upload["fields"],
            "storage_key": storage_key,
            "expires_in": 300,
            "max_bytes": 5 * 1024 * 1024,
            "required_content_type": content_type,
        }, status=status.HTTP_201_CREATED)


class PortalBankReceiptFinalizeAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, submission_id):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Only students can finalize their receipt upload.")
        with transaction.atomic():
            item = PortalPaymentSubmission.objects.select_for_update().select_related(
                "enrollment", "course"
            ).filter(pk=submission_id, student=request.user).first()
            if not item:
                raise NotFound("Receipt upload not found.")
            if item.status != PortalPaymentSubmission.UPLOADING:
                raise serializers.ValidationError({"status": "This receipt upload is not awaiting completion."})
            if not item.upload_expires_at or timezone.now() > item.upload_expires_at:
                raise serializers.ValidationError({"status": "Upload authorization expired. Request a new upload URL."})
            if item.enrollment.status != PortalEnrollment.PENDING or item.enrollment.course_id != item.course_id:
                raise serializers.ValidationError({"enrollment": "The related pending enrolment is no longer valid."})
            try:
                verify_uploaded_receipt(
                    storage_key=item.storage_key, owner_id=str(request.user.pk),
                    expected_content_type=item.content_type, max_bytes=5 * 1024 * 1024,
                )
            except ReceiptStorageError:
                raise PortalStorageUnavailable()
            item.status = PortalPaymentSubmission.PENDING
            item.upload_expires_at = None
            item.save(update_fields=["status", "upload_expires_at"])
            PortalAuditLog.objects.create(
                actor=request.user, action="payment_submission.receipt_uploaded",
                target_type="payment_submission", target_id=str(item.pk),
                metadata={"course_id": str(item.course_id), "content_type": item.content_type},
            )
        return Response({"id": str(item.pk), "status": item.status}, status=status.HTTP_200_OK)


class PortalBankReceiptAccessAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, submission_id):
        item = PortalPaymentSubmission.objects.select_related("student").filter(pk=submission_id).first()
        if not item:
            raise NotFound("Receipt not found.")
        if request.user.role != PortalIdentity.ROLE_ADMIN and item.student_id != request.user.pk:
            raise PermissionDenied("You cannot access another student's receipt.")
        if item.status not in [PortalPaymentSubmission.PENDING, PortalPaymentSubmission.APPROVED, PortalPaymentSubmission.REJECTED]:
            raise NotFound("Receipt is not available.")
        try:
            url = generate_receipt_download_url(
                storage_key=item.storage_key, file_name=item.file_name, expires_seconds=120,
            )
        except ReceiptStorageError:
            raise PortalStorageUnavailable()
        return Response({"download_url": url, "expires_in": 120})


class PortalAdminClassroomAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _admin(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")

    def get(self, request):
        self._admin(request)
        sessions = PortalClassroomSession.objects.select_related("course").annotate(
            attendance_count=models.Count("attendance")
        ).order_by("-starts_at")[:100]
        announcements = PortalClassroomAnnouncement.objects.select_related("course").order_by("-created_at")[:100]
        student_messages = PortalClassroomMessage.objects.select_related("course").order_by("-created_at")[:100]
        teacher_replies = PortalTeacherReply.objects.select_related("course").order_by("-created_at")[:100]
        messages = [{
            "id": str(item.pk), "course_id": str(item.course_id),
            "course_title": item.course.title, "author_role": item.author_role,
            "message": item.message, "created_at": item.created_at,
        } for item in student_messages]
        messages += [{
            "id": str(item.pk), "course_id": str(item.course_id),
            "course_title": item.course.title, "author_role": "teacher",
            "message": item.message, "created_at": item.created_at,
        } for item in teacher_replies]
        messages.sort(key=lambda item: item["created_at"], reverse=True)
        return Response({
            "sessions": [{
                "id": str(item.pk), "course_id": str(item.course_id),
                "course_title": item.course.title, "title": item.title,
                "description": item.description, "meeting_url": item.meeting_url,
                "starts_at": item.starts_at, "ends_at": item.ends_at,
                "status": item.status, "created_at": item.created_at,
                "attendance_count": item.attendance_count,
                "created_by": item.created_by_handle,
            } for item in sessions],
            "announcements": [{
                "id": str(item.pk), "course_id": str(item.course_id) if item.course_id else None,
                "course_title": item.course.title if item.course else None,
                "title": item.title, "body": item.body, "published": item.published,
                "created_at": item.created_at, "created_by": item.created_by_handle,
            } for item in announcements],
            "messages": messages[:100],
        })

    def post(self, request):
        self._admin(request)
        action = request.data.get("action")
        if action == "create_session":
            course_id = request.data.get("course_id")
            title = request.data.get("title")
            description = request.data.get("description", "")
            meeting_url = request.data.get("meeting_url")
            if not isinstance(title, str) or not title.strip() or len(title) > 180:
                raise serializers.ValidationError({"title": "Session title is required (maximum 180 characters)."})
            if not isinstance(description, str) or len(description) > 3000:
                raise serializers.ValidationError({"description": "Description must be text up to 3000 characters."})
            if not isinstance(meeting_url, str) or not meeting_url.startswith("https://"):
                raise serializers.ValidationError({"meeting_url": "Meeting links must use HTTPS."})
            course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
            if not course:
                raise NotFound("Active course not found.")
            try:
                starts_at = serializers.DateTimeField().run_validation(request.data.get("starts_at"))
                ends_at = serializers.DateTimeField().run_validation(request.data.get("ends_at"))
            except serializers.ValidationError:
                raise serializers.ValidationError({"starts_at": "Provide valid session start and end timestamps."})
            if ends_at <= starts_at:
                raise serializers.ValidationError({"ends_at": "Session end must be after its start."})
            item = PortalClassroomSession.objects.create(
                course=course, title=title.strip(), description=description.strip(),
                meeting_url=meeting_url, starts_at=starts_at, ends_at=ends_at,
                status="scheduled", created_by=request.user,
                created_by_handle=request.user.username,
            )
            PortalAuditLog.objects.create(
                actor=request.user, action="classroom_session_created",
                target_type="classroom_session", target_id=str(item.pk),
                metadata={"course_id": str(course.pk), "title": item.title},
            )
            return Response({"session": {
                "id": str(item.pk), "course_id": str(course.pk), "title": item.title,
                "description": item.description, "meeting_url": item.meeting_url,
                "starts_at": item.starts_at, "ends_at": item.ends_at, "status": item.status,
            }}, status=status.HTTP_201_CREATED)
        if action == "create_announcement":
            course_id = request.data.get("course_id")
            course = None
            if course_id:
                course = PortalCourse.objects.filter(pk=course_id).first()
                if not course:
                    raise NotFound("Course not found.")
            title, body = request.data.get("title"), request.data.get("body")
            if not isinstance(title, str) or not title.strip() or len(title) > 180:
                raise serializers.ValidationError({"title": "Announcement title is required (maximum 180 characters)."})
            if not isinstance(body, str) or not body.strip() or len(body) > 5000:
                raise serializers.ValidationError({"body": "Announcement text is required (maximum 5000 characters)."})
            item = PortalClassroomAnnouncement.objects.create(
                course=course, title=title.strip(), body=body.strip(),
                published=True, created_by=request.user, created_by_handle=request.user.username,
            )
            PortalAuditLog.objects.create(
                actor=request.user, action="classroom_announcement_created",
                target_type="classroom_announcement", target_id=str(item.pk),
                metadata={"course_id": str(course.pk) if course else None, "title": item.title},
            )
            return Response({"announcement": {
                "id": str(item.pk), "course_id": str(course.pk) if course else None,
                "title": item.title, "body": item.body, "published": item.published,
            }}, status=status.HTTP_201_CREATED)
        if action == "reply":
            course = PortalCourse.objects.filter(pk=request.data.get("course_id")).first()
            message = request.data.get("message")
            if not course:
                raise NotFound("Course not found.")
            if not isinstance(message, str) or not message.strip() or len(message) > 3000:
                raise serializers.ValidationError({"message": "Reply must contain 1 to 3000 characters."})
            item = PortalTeacherReply.objects.create(
                course=course, created_by=request.user,
                created_by_handle=request.user.username, message=message.strip(),
            )
            PortalAuditLog.objects.create(
                actor=request.user, action="classroom_teacher_reply_created",
                target_type="teacher_reply", target_id=str(item.pk),
                metadata={"course_id": str(course.pk)},
            )
            return Response({"message": {
                "id": str(item.pk), "course_id": str(course.pk),
                "message": item.message, "author_role": "teacher",
                "created_at": item.created_at,
            }}, status=status.HTTP_201_CREATED)
        raise serializers.ValidationError({"action": "Unknown classroom action."})

    def patch(self, request):
        self._admin(request)
        session_id = request.data.get("session_id")
        new_status = request.data.get("status")
        if new_status not in dict(PortalClassroomSession.STATUS_CHOICES):
            raise serializers.ValidationError({"status": "Choose a valid classroom session status."})
        with transaction.atomic():
            item = PortalClassroomSession.objects.select_for_update().filter(pk=session_id).first()
            if not item:
                raise NotFound("Class session not found.")
            previous = item.status
            item.status = new_status
            item.save(update_fields=["status", "updated_at"])
            PortalAuditLog.objects.create(
                actor=request.user, action="classroom_session_status_changed",
                target_type="classroom_session", target_id=str(item.pk),
                metadata={"from": previous, "to": new_status},
            )
        return Response({"session": {"id": str(item.pk), "status": item.status}})


class PortalStudentEnrollmentListAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        bank_status = PortalPaymentSubmission.objects.filter(
            enrollment_id=models.OuterRef("pk"), student=request.user
        ).order_by("-submitted_at").values("status")[:1]
        paystack_status = PortalPayment.objects.filter(
            enrollment_id=models.OuterRef("pk"), student=request.user
        ).order_by("-created_at").values("status")[:1]
        items = PortalEnrollment.objects.filter(student=request.user).select_related("course").annotate(
            latest_bank_status=models.Subquery(bank_status),
            latest_paystack_status=models.Subquery(paystack_status),
        ).order_by("-created_at")[:200]
        enrolments = []
        for item in items:
            payment_status = item.latest_bank_status or item.latest_paystack_status
            if payment_status == PortalPaymentSubmission.APPROVED:
                payment_status = "verified"
            enrolments.append({
                "id": str(item.pk), "course_id": str(item.course_id),
                "status": item.status, "enrolled_at": item.created_at,
                "title": item.course.title, "level": item.course.level,
                "fee_amount": str(item.course.fee_amount),
                "fee_currency": item.course.fee_currency,
                "payment_status": payment_status,
            })
        return Response({"enrolments": enrolments, "results": enrolments})


class PortalStudentPaymentAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_STUDENT:
            raise PermissionDenied("Student access only.")
        enrollment_id = request.query_params.get("enrollment_id")
        enrollment = PortalEnrollment.objects.select_related("course").filter(
            pk=enrollment_id, student=request.user
        ).first()
        if not enrollment:
            raise NotFound("Enrolment not found.")
        setting = PortalSiteSetting.objects.filter(setting_key="bank_transfer").first()
        payment = PortalPaymentSubmission.objects.filter(
            enrollment=enrollment, student=request.user
        ).order_by("-submitted_at").first()
        return Response({
            "enrolment": {
                "enrolment_id": str(enrollment.pk),
                "enrolment_status": enrollment.status,
                "course_id": str(enrollment.course_id),
                "title": enrollment.course.title,
                "fee_amount": str(enrollment.course.fee_amount),
                "fee_currency": enrollment.course.fee_currency,
            },
            "bank": setting.setting_value if setting else {},
            "payment": ({
                "id": str(payment.pk), "amount": str(payment.amount),
                "currency": payment.currency, "transfer_reference": payment.transfer_reference,
                "status": "verified" if payment.status == PortalPaymentSubmission.APPROVED else payment.status, "admin_note": payment.admin_note,
                "submitted_at": payment.submitted_at, "reviewed_at": payment.reviewed_at,
            } if payment else None),
        })


class PortalAdminPaymentsAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _admin(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")

    def get(self, request):
        self._admin(request)
        setting = PortalSiteSetting.objects.filter(setting_key="bank_transfer").first()
        courses = PortalCourse.objects.order_by("title")
        bank_payments = PortalPaymentSubmission.objects.select_related(
            "student", "course", "enrollment"
        ).order_by("-submitted_at")[:300]
        paystack = PortalPayment.objects.select_related(
            "student", "enrollment__course"
        ).order_by("-created_at")[:300]
        return Response({
            "bank": setting.setting_value if setting else {},
            "courses": [{
                "id": str(item.pk), "title": item.title,
                "fee_amount": str(item.fee_amount), "fee_currency": item.fee_currency,
                "active": item.is_active,
            } for item in courses],
            "payments": [{
                "id": str(item.pk), "enrolment_id": str(item.enrollment_id),
                "user_id": str(item.student_id), "course_id": str(item.course_id),
                "amount": str(item.amount), "currency": item.currency,
                "transfer_reference": item.transfer_reference,
                "storage_key": item.storage_key, "content_type": item.content_type,
                "file_name": item.file_name, "status": "verified" if item.status == PortalPaymentSubmission.APPROVED else item.status,
                "admin_note": item.admin_note, "submitted_at": item.submitted_at,
                "reviewed_at": item.reviewed_at,
                "course_title": item.course.title,
                "student_name": item.student.full_name or item.student.username,
                "email": item.student.email,
                "receipt_endpoint": f"/api/portal/v1/payment-submissions/{item.pk}/receipt/",
            } for item in bank_payments],
            "paystack_payments": [{
                "id": str(item.pk), "enrolment_id": str(item.enrollment_id),
                "user_id": str(item.student_id), "course_id": str(item.enrollment.course_id),
                "reference": item.reference, "amount_kobo": item.amount_kobo,
                "currency": item.currency, "status": item.status,
                "created_at": item.created_at, "verified_at": item.verified_at,
                "course_title": item.enrollment.course.title,
                "student_name": item.student.full_name or item.student.username,
                "email": item.student.email,
            } for item in paystack],
        })

    def post(self, request):
        self._admin(request)
        action = request.data.get("action")
        if action == "save_bank":
            bank_name = request.data.get("bank_name")
            account_name = request.data.get("account_name")
            account_number = request.data.get("account_number")
            instructions = request.data.get("instructions", "")
            if not all(isinstance(x, str) for x in [bank_name, account_name, account_number, instructions]):
                raise serializers.ValidationError({"detail": "Bank name, account name and account number are required."})
            bank_name, account_name = bank_name.strip()[:100], account_name.strip()[:140]
            account_number = "".join(ch for ch in account_number if ch.isdigit())[:40]
            instructions = instructions.strip()[:1000]
            if not bank_name or not account_name or not 8 <= len(account_number) <= 20:
                raise serializers.ValidationError({"detail": "Provide valid bank name, account name and account number."})
            value = {"bank_name": bank_name, "account_name": account_name, "account_number": account_number, "instructions": instructions}
            PortalSiteSetting.objects.update_or_create(
                setting_key="bank_transfer", defaults={"setting_value": value}
            )
            PortalAuditLog.objects.create(
                actor=request.user, action="bank_transfer_details_updated",
                target_type="site_settings", target_id="bank_transfer",
                metadata={"bank_name": bank_name, "account_number_last4": account_number[-4:]},
            )
            return Response({"message": "Bank transfer details saved.", "bank": value})
        if action == "set_fee":
            course_id = request.data.get("course_id")
            fee_amount = request.data.get("fee_amount")
            currency = str(request.data.get("fee_currency", "NGN")).upper()
            try:
                amount = int(fee_amount)
            except (TypeError, ValueError):
                raise serializers.ValidationError({"fee_amount": "Enter a whole-number NGN course fee."})
            if amount < 0 or amount > 100000000 or currency != "NGN":
                raise serializers.ValidationError({"fee_amount": "Enter a valid whole-number NGN course fee."})
            course = PortalCourse.objects.filter(pk=course_id).first()
            if not course:
                raise NotFound("Course not found.")
            course.fee_amount = Decimal(amount)
            course.fee_currency = currency
            course.save(update_fields=["fee_amount", "fee_currency", "updated_at"])
            PortalAuditLog.objects.create(
                actor=request.user, action="course_fee_updated",
                target_type="course", target_id=str(course.pk),
                metadata={"fee_amount": amount, "fee_currency": currency},
            )
            return Response({"course": {"id": str(course.pk), "title": course.title, "fee_amount": str(course.fee_amount), "fee_currency": course.fee_currency}})
        if action == "review":
            submission_id = request.data.get("payment_id")
            review_status = request.data.get("status")
            mapped_status = PortalPaymentSubmission.APPROVED if review_status == "verified" else review_status
            forwarded = SimpleNamespace(user=request.user, data={**dict(request.data), "status": mapped_status, "admin_note": request.data.get("admin_note", "")})
            return PortalAdminPaymentSubmissionAPIView().post(forwarded, submission_id)
        raise serializers.ValidationError({"action": "Unknown payment action."})


class PortalAdminPaystackPaymentAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        items = PortalPayment.objects.select_related(
            "student", "enrollment__course"
        ).order_by("-created_at")[:200]
        return Response({"results": [{
            "id": str(item.pk),
            "reference": item.reference,
            "student_email": item.student.email,
            "student_name": item.student.full_name or item.student.username,
            "course_title": item.enrollment.course.title,
            "amount_kobo": item.amount_kobo,
            "currency": item.currency,
            "status": item.status,
            "created_at": item.created_at,
            "verified_at": item.verified_at,
        } for item in items]})


class PortalAdminPaymentSubmissionAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        state = request.query_params.get("status", PortalPaymentSubmission.PENDING)
        if state not in dict(PortalPaymentSubmission.STATUS_CHOICES):
            raise serializers.ValidationError({"status": "Invalid bank payment status."})
        items = PortalPaymentSubmission.objects.filter(status=state).select_related(
            "student", "course", "enrollment", "reviewed_by"
        )[:200]
        return Response({"results": [{
            "id": str(item.pk),
            "enrollment_id": str(item.enrollment_id),
            "student_id": str(item.student_id),
            "student_name": item.student.full_name or item.student.username,
            "student_email": item.student.email,
            "course_id": str(item.course_id),
            "course_title": item.course.title,
            "amount": str(item.amount),
            "currency": item.currency,
            "transfer_reference": item.transfer_reference,
            "storage_key": item.storage_key,
            "content_type": item.content_type,
            "file_name": item.file_name,
            "status": item.status,
            "admin_note": item.admin_note,
            "submitted_at": item.submitted_at,
            "reviewed_at": item.reviewed_at,
        } for item in items]})

    def post(self, request, submission_id):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        new_status = request.data.get("status")
        note = request.data.get("admin_note", "")
        if new_status not in [PortalPaymentSubmission.APPROVED, PortalPaymentSubmission.REJECTED]:
            raise serializers.ValidationError({"status": "Choose approved or rejected."})
        if not isinstance(note, str) or len(note) > 2000:
            raise serializers.ValidationError({"admin_note": "Note must be text up to 2000 characters."})
        with transaction.atomic():
            item = PortalPaymentSubmission.objects.select_for_update().select_related(
                "student", "course", "enrollment"
            ).filter(pk=submission_id).first()
            if not item:
                raise NotFound("Bank payment submission not found.")
            if item.student_id == request.user.pk:
                raise PermissionDenied("An administrator cannot review their own payment submission.")
            if item.status != PortalPaymentSubmission.PENDING:
                raise serializers.ValidationError({"status": "Only pending submissions can be reviewed."})
            if item.enrollment.student_id != item.student_id or item.enrollment.course_id != item.course_id:
                raise serializers.ValidationError({"detail": "Payment submission ownership does not match its enrolment."})
            if item.enrollment.status != PortalEnrollment.PENDING:
                raise serializers.ValidationError({"detail": "Only a pending enrolment can be approved by bank payment review."})
            if new_status == PortalPaymentSubmission.APPROVED and (
                item.amount != item.course.fee_amount or item.currency != item.course.fee_currency
            ):
                raise serializers.ValidationError({"detail": "Receipt amount or currency does not match the stored course fee."})
            if new_status == PortalPaymentSubmission.APPROVED and (
                not item.storage_key or not item.storage_key.startswith(f"{item.student_id}/")
            ):
                raise serializers.ValidationError({"detail": "Receipt storage ownership is invalid."})
            if new_status == PortalPaymentSubmission.APPROVED:
                try:
                    verify_uploaded_receipt(
                        storage_key=item.storage_key, owner_id=str(item.student_id),
                        expected_content_type=item.content_type, max_bytes=5 * 1024 * 1024,
                    )
                except ReceiptStorageError:
                    raise PortalStorageUnavailable()
            item.status = new_status
            item.admin_note = note.strip()
            item.reviewed_at = timezone.now()
            item.reviewed_by = request.user
            item.save(update_fields=["status", "admin_note", "reviewed_at", "reviewed_by"])
            if new_status == PortalPaymentSubmission.APPROVED:
                item.enrollment.status = PortalEnrollment.APPROVED
                item.enrollment.save(update_fields=["status", "updated_at"])
            PortalAuditLog.objects.create(
                actor=request.user, action="payment_submission.reviewed",
                target_type="payment_submission", target_id=str(item.pk),
                metadata={"from": PortalPaymentSubmission.PENDING, "to": new_status,
                          "student_id": str(item.student_id), "course_id": str(item.course_id),
                          "note": note.strip()},
            )
        return Response({"id": str(item.pk), "status": item.status, "reviewed_at": item.reviewed_at})


class PortalAdminPracticeReviewAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        state = request.query_params.get("status")
        if state and state not in dict(PortalPracticeSubmission.STATUS_CHOICES):
            raise serializers.ValidationError({"status": "Invalid practice status."})
        items = PortalPracticeSubmission.objects.all()
        if state:
            items = items.filter(status=state)
        items = items.select_related("student", "reviewed_by").order_by(
            models.Case(
                models.When(status="submitted", then=0),
                models.When(status="in_review", then=1),
                default=2, output_field=models.IntegerField(),
            ), "-submitted_at"
        )[:300]
        results = [{
            "id": str(item.pk),
            "student_id": str(item.student_id),
            "student_name": item.student.full_name or item.student.username,
            "student_email": item.student.email,
            "lab_key": item.lab_key,
            "title": item.title,
            "submission_text": item.submission_text,
            "project_url": item.project_url,
            "status": item.status,
            "reviewer_notes": item.reviewer_notes,
            "submitted_at": item.submitted_at,
            "reviewed_at": item.reviewed_at,
            "reviewed_by": item.reviewed_by.username if item.reviewed_by else None,
        } for item in items]
        return Response({"submissions": results, "results": results})

    def post(self, request, submission_id):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        new_status = request.data.get("status")
        notes = request.data.get("reviewer_notes", "")
        if new_status not in ["in_review", "approved", "needs_changes"]:
            raise serializers.ValidationError({"status": "Choose in_review, approved or needs_changes."})
        if not isinstance(notes, str) or len(notes) > 2000:
            raise serializers.ValidationError({"reviewer_notes": "Notes must be text up to 2000 characters."})
        with transaction.atomic():
            item = PortalPracticeSubmission.objects.select_for_update().filter(pk=submission_id).first()
            if not item:
                raise NotFound("Practice submission not found.")
            if item.student_id == request.user.pk:
                raise PermissionDenied("An administrator cannot review their own submission.")
            previous = item.status
            item.status = new_status
            item.reviewer_notes = notes.strip()
            item.reviewed_at = timezone.now()
            item.reviewed_by = request.user
            item.save(update_fields=["status", "reviewer_notes", "reviewed_at", "reviewed_by"])
            PortalAuditLog.objects.create(
                actor=request.user, action="practice.reviewed",
                target_type="practice_submission", target_id=str(item.pk),
                metadata={"from": previous, "to": new_status, "student_id": str(item.student_id)},
            )
        return Response({"id": str(item.pk), "status": item.status, "reviewed_at": item.reviewed_at})


class PortalAdminAuditLogAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        events = PortalAuditLog.objects.select_related("actor")[:200]
        return Response({"results": [{
            "id": str(item.pk),
            "actor_id": str(item.actor_id),
            "actor_username": item.actor.username if item.actor else item.actor_handle,
            "action": item.action,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "metadata": item.metadata,
            "created_at": item.created_at,
        } for item in events]})


class PortalAdminOverviewAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        return Response({
            "students_count": PortalIdentity.objects.filter(role=PortalIdentity.ROLE_STUDENT).count(),
            "active_courses_count": PortalCourse.objects.filter(is_active=True).count(),
            "enrollments_count": PortalEnrollment.objects.count(),
            "pending_enrollments_count": PortalEnrollment.objects.filter(status=PortalEnrollment.PENDING).count(),
            "pending_paystack_count": PortalPayment.objects.filter(status=PortalPayment.PENDING).count(),
            "pending_bank_payments_count": PortalPaymentSubmission.objects.filter(status=PortalPaymentSubmission.PENDING).count(),
            "submitted_practice_count": PortalPracticeSubmission.objects.filter(status="submitted").count(),
            "certificates_count": PortalCertificate.objects.count(),
        })


class PortalAdminStudentListAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        records = PortalIdentity.objects.filter(role=PortalIdentity.ROLE_STUDENT).annotate(
            enrollment_count=models.Count("enrollments")
        ).order_by("-created_at")[:100]
        return Response({"results": [{
            "user_id": str(item.pk),
            "email": item.email,
            "username": item.username,
            "full_name": item.full_name,
            "phone": item.phone,
            "role": item.role,
            "created_at": item.created_at,
            "enrollment_count": item.enrollment_count,
        } for item in records]})


class PortalAdminCourseInstructorAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        assignments = PortalCourseInstructor.objects.select_related("course", "instructor", "assigned_by")[:300]
        return Response({"results": [{
            "id": str(item.pk),
            "course_id": str(item.course_id),
            "course_title": item.course.title,
            "instructor_id": str(item.instructor_id),
            "instructor_name": item.instructor.full_name or item.instructor.username,
            "instructor_email": item.instructor.email,
            "assigned_at": item.created_at,
        } for item in assignments]})

    def post(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        course_id = request.data.get("course_id")
        instructor_id = request.data.get("instructor_id")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        instructor = PortalIdentity.objects.filter(pk=instructor_id, role=PortalIdentity.ROLE_INSTRUCTOR, is_active=True).first()
        if not course or not instructor:
            raise serializers.ValidationError({"detail": "Choose an active course and an active instructor account."})
        assignment, created = PortalCourseInstructor.objects.get_or_create(
            course=course, instructor=instructor, defaults={"assigned_by": request.user}
        )
        if created:
            PortalAuditLog.objects.create(
                actor=request.user, action="course.instructor_assigned",
                target_type="course_instructor", target_id=str(assignment.pk),
                metadata={"course_id": str(course.pk), "instructor_id": str(instructor.pk)},
            )
        return Response({"id": str(assignment.pk), "course_id": str(course.pk), "instructor_id": str(instructor.pk), "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, assignment_id):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        assignment = PortalCourseInstructor.objects.filter(pk=assignment_id).first()
        if not assignment:
            raise NotFound("Instructor assignment not found.")
        course_id, instructor_id = str(assignment.course_id), str(assignment.instructor_id)
        PortalCourseInstructor.objects.filter(pk=assignment.pk).delete()
        PortalAuditLog.objects.create(
            actor=request.user, action="course.instructor_unassigned",
            target_type="course_instructor", target_id=str(assignment.pk),
            metadata={"course_id": course_id, "instructor_id": instructor_id},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PortalInstructorCoursesAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_INSTRUCTOR:
            raise PermissionDenied("Instructor access only.")
        courses = PortalCourse.objects.filter(
            instructor_assignments__instructor=request.user, is_active=True
        ).distinct().order_by("title")
        return Response({"results": [{
            "id": str(course.pk), "title": course.title,
            "description": course.description, "level": course.level,
            "students_count": PortalEnrollment.objects.filter(
                course=course, status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED]
            ).count(),
        } for course in courses]})


class PortalInstructorStudentListAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_INSTRUCTOR:
            raise PermissionDenied("Instructor access only.")
        assigned = PortalCourseInstructor.objects.filter(course_id=course_id, instructor=request.user).exists()
        if not assigned:
            raise PermissionDenied("This course is not assigned to your instructor account.")
        enrollments = PortalEnrollment.objects.filter(
            course_id=course_id, status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED]
        ).select_related("student")[:200]
        return Response({"results": [{
            "student_id": str(item.student_id),
            "full_name": item.student.full_name or item.student.username,
            "email": item.student.email,
            "enrollment_status": item.status,
        } for item in enrollments]})
