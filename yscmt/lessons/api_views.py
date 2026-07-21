from rest_framework import generics
from .models import Lesson
from .serializers import LessonSerializer


class LessonListAPIView(generics.ListAPIView):
    serializer_class = LessonSerializer

    def get_queryset(self):
        course = self.request.GET.get("course")

        if course:
            return Lesson.objects.filter(course_id=course)

        return Lesson.objects.all()


class LessonDetailAPIView(generics.RetrieveAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
