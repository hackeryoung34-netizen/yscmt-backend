from django.db import IntegrityError, transaction
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from .authentication import PortalJWTAuthentication
from .models import PortalIdentity, PortalCourse, PortalLesson, PortalEnrollment, PortalLessonProgress
from .serializers import PortalRegisterSerializer, PortalTokenSerializer, PortalCourseSerializer, PortalLessonSerializer, PortalEnrollmentCreateSerializer

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
