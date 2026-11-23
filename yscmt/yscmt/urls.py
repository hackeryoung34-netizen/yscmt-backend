from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView
from student_portal.views import PortalRegisterAPIView, PortalTokenObtainPairView


def home(request):
    return JsonResponse({
        "status": "success",
        "message": "YSCMT Backend API is running",
        "api": "/api/",
    })


urlpatterns = [
    path("", home),
    path("admin/", admin.site.urls),

    # Student Portal routes use the isolated portal identity store.
    path("api/portal/v1/", include("student_portal.urls")),
    path("api/auth/register/", PortalRegisterAPIView.as_view()),

    # Legacy account endpoints remain available on this preview branch.
    path("api/auth/", include("accounts.urls")),

    # Preserve the React frontend's existing token and refresh URL contract.
    path("api/token/", PortalTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Legacy Django application endpoints.
    path("api/courses/", include("courses.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/lessons/", include("lessons.urls")),
    path("api/progress/", include("progress.urls")),
    path("api/enrollments/", include("enrollments.urls")),
    path("api/certificates/", include("certificates.urls")),
    path("api/", include("quizzes.urls")),
    path("api/", include("quiz_questions.urls")),
    path("api/", include("quiz_attempts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
