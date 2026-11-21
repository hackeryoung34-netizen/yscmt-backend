from rest_framework import serializers

from enrollments.models import Enrollment
from .models import LessonProgress


class LessonProgressSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)
    course_name = serializers.CharField(source="lesson.course.name", read_only=True)

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
        read_only_fields = ["id", "completed_at"]

    def validate_lesson(self, lesson):
        request = self.context.get("request")
        if request and not Enrollment.objects.filter(
            student=request.user,
            course=lesson.course,
        ).exists():
            raise serializers.ValidationError(
                "You must be enrolled in this course to record lesson progress."
            )
        return lesson
