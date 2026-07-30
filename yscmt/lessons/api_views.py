from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Lesson
from .serializers import LessonSerializer


class LessonListAPIView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):

        course_id = request.GET.get("course")

        lessons = Lesson.objects.all()

        if course_id:
            lessons = lessons.filter(course_id=course_id)

        serializer = LessonSerializer(
            lessons,
            many=True
        )

        return Response(serializer.data)


class LessonDetailAPIView(APIView):

    permission_classes = [AllowAny]

    def get(self, request, pk):

        try:
            lesson = Lesson.objects.get(pk=pk)

        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=404
            )

        serializer = LessonSerializer(lesson)

        return Response(serializer.data)
