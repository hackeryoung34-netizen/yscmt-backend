from rest_framework import viewsets

from .models import Quiz
from .serializers import QuizSerializer
from yscmt.permissions import IsAdminUserOrReadOnly


class QuizViewSet(viewsets.ModelViewSet):
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    permission_classes = [IsAdminUserOrReadOnly]
