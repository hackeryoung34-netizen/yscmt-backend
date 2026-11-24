from django.db import IntegrityError, transaction
from datetime import timedelta
from rest_framework import generics, serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from .authentication import PortalJWTAuthentication
from .models import (PortalIdentity, PortalCourse, PortalLesson, PortalEnrollment, PortalLessonProgress, PortalExam, PortalExamQuestion, PortalExamSession, PortalExamAttempt)
from .serializers import PortalRegisterSerializer, PortalTokenSerializer, PortalCourseSerializer, PortalLessonSerializer, PortalEnrollmentCreateSerializer, PortalExamSubmitSerializer

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
