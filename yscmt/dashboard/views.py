from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from quiz_attempts.models import QuizAttempt
from certificates.models import Certificate
from enrollments.models import Enrollment


class DashboardAPIView(APIView):

    permission_classes = [IsAuthenticated]


    def get(self, request):

        user = request.user


        return Response({

            "student":
                user.username,

            "courses_enrolled":
                Enrollment.objects.filter(
                    student=user
                ).count(),

            "quiz_attempts":
                QuizAttempt.objects.filter(
                    student=user
                ).count(),

            "certificates":
                Certificate.objects.filter(
                    student=user
                ).count()
        })
