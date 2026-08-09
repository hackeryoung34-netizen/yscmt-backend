from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Quiz

class QuizAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):

        quiz = Quiz.objects.filter(
            course_id=course_id
        ).first()

        return Response({

            "id": quiz.id,
            "title": quiz.title

        })
