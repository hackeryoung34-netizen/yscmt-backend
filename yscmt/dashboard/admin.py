from django.contrib import admin
from django.contrib.auth.models import User

from courses.models import Course
from lessons.models import Lesson
from enrollments.models import Enrollment
from certificates.models import Certificate
from quizzes.models import Quiz


admin.site.index_template = "admin/index.html"
