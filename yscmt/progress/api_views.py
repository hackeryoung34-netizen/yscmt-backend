from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import LessonProgress
from .serializers import LessonProgressSerializer

from lessons.models import Lesson
from certificates.models import Certificate
from enrollments.models import Enrollment

from uuid import uuid4


class LessonProgressListAPIView(generics.ListAPIView):
    serializer_class = LessonProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            LessonProgress.objects
            .filter(student=self.request.user)
            .select_related("lesson", "lesson__course")
            .order_by("lesson__order")
        )


class LessonProgressAPIView(generics.GenericAPIView):
    serializer_class = LessonProgressSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        try:
            lesson = Lesson.objects.select_related("course").get(
                id=lesson_id
            )
        except Lesson.DoesNotExist:
            return Response(
                {
                    "detail": "Lesson not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        is_enrolled = Enrollment.objects.filter(
            student=request.user,
            course=lesson.course,
        ).exists()

        if not is_enrolled:
            return Response(
                {
                    "detail": "You must be enrolled in this course to record lesson progress."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        progress, created = LessonProgress.objects.get_or_create(
            student=request.user,
            lesson=lesson,
            defaults={
                "completed": True,
            },
        )

        if not progress.completed:
            progress.completed = True
            progress.save()

        course = lesson.course

        # Get all lessons belonging to this course
        total_lessons = Lesson.objects.filter(
            course=course
        ).count()

        completed_lessons = LessonProgress.objects.filter(
            student=request.user,
            lesson__course=course,
            completed=True,
        ).count()

        certificate = None

        # Issue certificate only when every lesson is completed
        if total_lessons > 0 and completed_lessons >= total_lessons:
            certificate, certificate_created = (
                Certificate.objects.get_or_create(
                    student=request.user,
                    course=course,
                    defaults={
                        "certificate_number": (
                            f"YSCMT-{uuid4().hex[:8].upper()}"
                        )
                    },
                )
            )

        serializer = self.get_serializer(progress)

        return Response(
            {
                "message": "Lesson completed successfully.",
                "progress": serializer.data,
                "course": {
                    "id": course.id,
                    "name": course.name,
                },
                "course_progress": {
                    "completed_lessons": completed_lessons,
                    "total_lessons": total_lessons,
                    "percentage": round(
                        (completed_lessons / total_lessons) * 100,
                        2
                    ) if total_lessons else 0,
                },
                "certificate": (
                    {
                        "id": certificate.id,
                        "certificate_number": (
                            certificate.certificate_number
                        ),
                    }
                    if certificate
                    else None
                ),
            },
            status=status.HTTP_200_OK,
        )
