from rest_framework import serializers
from .models import Enrollment
from payments.models import Payment


class EnrollmentSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(
        source="course.name",
        read_only=True
    )

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "course",
            "course_name",
            "student",
            "enrolled_at"
        ]
        read_only_fields = [
            "student",
            "enrolled_at"
        ]

    def validate_course(self, course):
        request = self.context.get("request")
        if request and not request.user.is_staff and course.price > 0:
            has_paid = Payment.objects.filter(
                student=request.user,
                course=course,
                status="paid"
            ).exists()
            if not has_paid:
                raise serializers.ValidationError(
                    "Payment must be confirmed before enrolling in this paid course."
                )
        return course
