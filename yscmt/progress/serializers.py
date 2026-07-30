from rest_framework import serializers

from .models import LessonProgress


class LessonProgressSerializer(serializers.ModelSerializer):

    lesson_title = serializers.CharField(
        source="lesson.title",
        read_only=True
    )

    course_name = serializers.CharField(
        source="lesson.course.name",
        read_only=True
    )


    class Meta:
        model = LessonProgress

        fields = [
            "id",
            "lesson",
            "lesson_title",
            "course_name",
            "completed",
            "completed_at",
        ]

        read_only_fields = [
            "id",
            "student",
            "completed_at",
        ]
