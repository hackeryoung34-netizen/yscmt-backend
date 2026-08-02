from django.contrib import admin
from .models import LessonProgress


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "lesson",
        "completed",
        "completed_at",
    )

    list_filter = (
        "completed",
        "lesson",
    )

    search_fields = (
        "student__username",
        "lesson__title",
    )

    ordering = ("-completed_at",)
