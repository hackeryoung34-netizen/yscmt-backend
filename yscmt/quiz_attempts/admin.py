from django.contrib import admin
from .models import QuizAttempt


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "quiz",
        "score",
        "completed",
        "attempted_at",
    )

    list_filter = (
        "completed",
        "quiz",
    )

    search_fields = (
        "student__username",
        "quiz__title",
    )

    ordering = ("-attempted_at",)
