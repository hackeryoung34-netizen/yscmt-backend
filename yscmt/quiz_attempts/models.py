from django.db import models
from django.contrib.auth.models import User
from quizzes.models import Quiz
from certificates.models import Certificate
import uuid


class QuizAttempt(models.Model):

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="quiz_attempts"
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="attempts"
    )

    score = models.IntegerField(default=0)

    completed = models.BooleanField(
        default=False
    )

    attempted_at = models.DateTimeField(
        auto_now_add=True
    )


    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)

        if self.completed and self.score >= 50:

            Certificate.objects.get_or_create(
                student=self.student,
                course=self.quiz.course,
                defaults={
                    "certificate_number": str(uuid.uuid4())
                }
            )


    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"
