from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from courses.models import Course
from lessons.models import Lesson
from certificates.models import Certificate
from quiz_attempts.models import QuizAttempt
from payments.models import Payment


class AdminDashboardAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        data = {
            "courses": Course.objects.count(),
            "lessons": Lesson.objects.count(),
            "students": User.objects.count(),
            "quiz_attempts": QuizAttempt.objects.count(),
            "certificates": Certificate.objects.count(),
            "payments": Payment.objects.count(),
        }

        return Response(data)
