from django.urls import path
from .api_views import (
    CourseListAPIView,
    CourseDetailAPIView,
)

urlpatterns = [
    path("", CourseListAPIView.as_view(), name="course-list"),
    path("<int:pk>/", CourseDetailAPIView.as_view(), name="course-detail"),
]
