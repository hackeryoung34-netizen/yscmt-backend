from rest_framework import serializers
from .models import Enrollment


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
