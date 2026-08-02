from django.contrib import admin
from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "quiz",
        "correct_answer",
    )

    list_filter = (
        "quiz",
        "correct_answer",
    )

    search_fields = (
        "text",
        "quiz__title",
    )
