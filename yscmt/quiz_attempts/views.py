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

    def get_queryset(self):
        return QuizAttempt.objects.filter(
            student=self.request.user
        )

    def create(self, request, *args, **kwargs):

        quiz_id = request.data.get("quiz")
        answers = request.data.get("answers", {})

        try:
            quiz = Quiz.objects.get(id=quiz_id)
        except Quiz.DoesNotExist:
            return Response(
                {"error": "Quiz not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        questions = Question.objects.filter(quiz=quiz)

        total = questions.count()
        correct = 0

        for question in questions:

            if (
                answers.get(str(question.id))
                == question.correct_answer
            ):
                correct += 1

        score = 0

        if total > 0:
            score = int((correct / total) * 100)

        attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            score=score,
            completed=True
        )

        serializer = self.get_serializer(attempt)

        return Response(serializer.data)
