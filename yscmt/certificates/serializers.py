from rest_framework import serializers

from .models import Certificate


class CertificateSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(
        source="course.name",
        read_only=True
    )

    class Meta:
        model = Certificate

        fields = [
            "id",
            "certificate_number",
            "issued_at",
            "student",
            "course",
            "course_name",
        ]

        read_only_fields = [
            "id",
            "certificate_number",
            "issued_at",
            "student",
            "course_name",
        ]
