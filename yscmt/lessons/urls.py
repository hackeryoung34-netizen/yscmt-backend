from django.urls import path
from .api_views import (
    LessonListAPIView,
    LessonDetailAPIView,
)

urlpatterns = [
    path("", LessonListAPIView.as_view()),
    path("<int:pk>/", LessonDetailAPIView.as_view()),
]
