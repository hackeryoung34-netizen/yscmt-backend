from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from enrollments.models import Enrollment
from certificates.models import Certificate
from progress.models import LessonProgress
from quiz_attempts.models import QuizAttempt


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0


class CertificateInline(admin.TabularInline):
    model = Certificate
    extra = 0
    readonly_fields = (
        "certificate_number",
        "course",
        "issued_at",
    )


class ProgressInline(admin.TabularInline):
    model = LessonProgress
    extra = 0


class QuizAttemptInline(admin.TabularInline):
    model = QuizAttempt
    extra = 0


admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    inlines = [
        EnrollmentInline,
        ProgressInline,
        QuizAttemptInline,
        CertificateInline,
    ]
