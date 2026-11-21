from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from accounts.views import AdminStudentListAPIView


def home(request):
    return JsonResponse({
        "status": "success",
        "message": "YSCMT Backend API is running",
        "api": "/api/"
    })


urlpatterns = [
    path("", home),
    path("admin/", admin.site.urls),

    # Authentication
    path("api/auth/", include("accounts.urls")),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Staff-only student directory
    path("api/students/", AdminStudentListAPIView.as_view(), name="admin-student-list"),

    # Main Apps
    path("api/courses/", include("courses.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/lessons/", include("lessons.urls")),
    path("api/progress/", include("progress.urls")),
    path("api/enrollments/", include("enrollments.urls")),
    path("api/certificates/", include("certificates.urls")),

    # Quiz System
    path("api/", include("quizzes.urls")),
    path("api/", include("quiz_questions.urls")),
    path("api/", include("quiz_attempts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
