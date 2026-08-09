from django.urls import path

from .api_views import (
    LessonProgressListAPIView,
    LessonProgressAPIView,
)

urlpatterns = [
    path(
        "",
        LessonProgressListAPIView.as_view(),
        name="progress-list",
    ),

    path(
        "<int:lesson_id>/complete/",
        LessonProgressAPIView.as_view(),
        name="lesson-complete",
    ),
]
