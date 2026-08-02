from django.contrib import admin
from .models import Quiz
from quiz_questions.models import Question


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
    )

    search_fields = (
        "title",
        "course__name",
    )

    list_filter = (
        "course",
    )

    inlines = [
        QuestionInline,
    ]
