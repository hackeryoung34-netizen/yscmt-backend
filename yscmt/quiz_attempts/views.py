from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import QuizAttempt
from .serializers import QuizAttemptSerializer
from quizzes.models import Quiz
from quiz_questions.models import Question


class QuizAttemptViewSet(viewsets.ModelViewSet):
    serializer_class = QuizAttemptSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return QuizAttempt.objects.filter(student=self.request.user)

    def create(self, request, *args, **kwargs):
        quiz_id = request.data.get("quiz")
        answers = request.data.get("answers", {})

        if not isinstance(answers, dict):
            return Response(
                {"error": "Answers must be provided as an object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quiz = Quiz.objects.get(id=quiz_id)
        except (Quiz.DoesNotExist, TypeError, ValueError):
            return Response(
                {"error": "Quiz not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        questions = Question.objects.filter(quiz=quiz)
        total = questions.count()
        correct = sum(
            1 for question in questions
            if answers.get(str(question.id)) == question.correct_answer
        )
        score = int((correct / total) * 100) if total else 0

        attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            score=score,
            completed=True,
        )
        serializer = self.get_serializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
