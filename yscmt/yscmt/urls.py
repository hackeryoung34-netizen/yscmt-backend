from django.contrib import admin
from django.urls import path, include

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


urlpatterns = [

    path("admin/", admin.site.urls),

    # Authentication
    path("api/auth/", include("accounts.urls")),

    # JWT Login
    path(
        "api/token/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair"
    ),

    path(
        "api/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh"
    ),

    # Main apps
    path("api/courses/", include("courses.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/lessons/", include("lessons.urls")),
    path("api/progress/", include("progress.urls")),
    path("api/enrollments/", include("enrollments.urls")),
    path("api/certificates/", include("certificates.urls")),

    # Quiz system
    path("api/", include("quizzes.urls")),
    path("api/", include("quiz_questions.urls")),
    path("api/", include("quiz_attempts.urls")),

]
