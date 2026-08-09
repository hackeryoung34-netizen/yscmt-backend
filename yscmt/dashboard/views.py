from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from courses.models import Course
from lessons.models import Lesson
from enrollments.models import Enrollment
from payments.models import Payment
from progress.models import LessonProgress
from quiz_attempts.models import QuizAttempt
from certificates.models import Certificate


class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # -------------------------------------------------
        # Student enrollments
        # -------------------------------------------------
        enrollments = Enrollment.objects.filter(
            student=user
        ).select_related("course")

        enrolled_courses = enrollments.count()

        enrolled_course_ids = enrollments.values_list(
            "course_id",
            flat=True
        )

        # -------------------------------------------------
        # Course / lesson statistics
        # -------------------------------------------------
        total_courses = Course.objects.count()

        total_lessons = Lesson.objects.filter(
            course_id__in=enrolled_course_ids
        ).count()

        completed_lessons = LessonProgress.objects.filter(
            student=user,
            completed=True,
            lesson__course_id__in=enrolled_course_ids,
        ).count()

        progress = 0

        if total_lessons > 0:
            progress = round(
                (completed_lessons / total_lessons) * 100,
                2
            )

        # -------------------------------------------------
        # Quiz statistics
        # -------------------------------------------------
        total_attempts = QuizAttempt.objects.filter(
            student=user
        ).count()

        completed_attempts = QuizAttempt.objects.filter(
            student=user,
            completed=True
        ).count()

        # -------------------------------------------------
        # Certificates
        # -------------------------------------------------
        certificates_queryset = Certificate.objects.filter(
            student=user
        ).select_related("course").order_by("-issued_at")

        certificates = certificates_queryset.count()

        certificate_data = [
            {
                "id": certificate.id,
                "certificate_number": certificate.certificate_number,
                "course_id": certificate.course_id,
                "course_name": certificate.course.name,
                "issued_at": certificate.issued_at,
            }
            for certificate in certificates_queryset
        ]

        # -------------------------------------------------
        # Payments
        # -------------------------------------------------
        paid_payments = Payment.objects.filter(
            student=user,
            status="paid"
        )

        total_paid = (
            paid_payments.aggregate(
                total=Sum("amount")
            )["total"] or 0
        )

        # -------------------------------------------------
        # Recent enrollments
        # -------------------------------------------------
        recent_courses = list(
            enrollments
            .order_by("-enrolled_at")[:5]
            .values(
                "course__name",
                "enrolled_at"
            )
        )

        # -------------------------------------------------
        # Response
        # -------------------------------------------------
        return Response({
            "student": user.username,

            "overview": {
                "total_courses": total_courses,
                "courses_enrolled": enrolled_courses,
                "total_lessons": total_lessons,
                "completed_lessons": completed_lessons,
                "progress": progress,
            },

            "quizzes": {
                "attempts": total_attempts,
                "completed": completed_attempts,
            },

            "certificates": certificates,

            "certificate_list": certificate_data,

            "payments": {
                "count": paid_payments.count(),
                "total_paid": total_paid,
            },

            "recent_courses": recent_courses,
        })
