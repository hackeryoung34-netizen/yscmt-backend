from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import LessonProgress
from .serializers import LessonProgressSerializer


class ProgressListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = LessonProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LessonProgress.objects.filter(
            student=self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(
            student=self.request.user,
            completed=True
        )


class ProgressDetailAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = LessonProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LessonProgress.objects.filter(
            student=self.request.user
        )
