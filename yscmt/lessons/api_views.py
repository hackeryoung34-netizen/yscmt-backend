from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Lesson
from .serializers import LessonSerializer


class LessonListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lessons = Lesson.objects.select_related("course")

        if not request.user.is_staff:
            lessons = lessons.filter(
                course__enrollments__student=request.user
            )

        course_id = request.GET.get("course")
        if course_id:
            lessons = lessons.filter(course_id=course_id)

        serializer = LessonSerializer(
            lessons.distinct(),
            many=True
        )
        return Response(serializer.data)


class LessonDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        lessons = Lesson.objects.select_related("course")

        if not request.user.is_staff:
            lessons = lessons.filter(
                course__enrollments__student=request.user
            )

        try:
            lesson = lessons.get(pk=pk)
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=404
            )

        serializer = LessonSerializer(lesson)
        return Response(serializer.data)
