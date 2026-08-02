from django.contrib import admin
from .models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "price",
        "total_lessons",
        "total_students",
        "total_quizzes",
    )

    search_fields = (
        "name",
    )

    def total_lessons(self, obj):
        return obj.lessons.count()

    def total_students(self, obj):
        return obj.enrollments.count()

    def total_quizzes(self, obj):
        return obj.quizzes.count()

    total_lessons.short_description = "Lessons"
    total_students.short_description = "Students"
    total_quizzes.short_description = "Quizzes"
