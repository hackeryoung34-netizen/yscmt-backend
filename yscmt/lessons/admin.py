from django.contrib import admin
from .models import Lesson


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "course",
        "created_at",
    )

    search_fields = (
        "title",
        "course__name",
    )

    list_filter = (
        "course",
    )

    ordering = (
        "course",
        "title",
    )
