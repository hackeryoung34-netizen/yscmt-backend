from rest_framework import generics
from .models import Course
from .serializers import CourseSerializer


class CourseListAPIView(generics.ListAPIView):
    serializer_class = CourseSerializer

    def get_queryset(self):
        qs = Course.objects.all()

        print("=" * 50)
        print("COURSE COUNT:", qs.count())
        print("DATABASE ALIAS:", qs.db)
        print("DATABASE FILE:", Course.objects.db)
        print("=" * 50)

        return qs


class CourseDetailAPIView(generics.RetrieveAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
