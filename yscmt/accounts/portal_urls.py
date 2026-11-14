"""URL namespace for the independent portal API only."""
from django.urls import path

from .portal_views import (
    PortalCourseDetailAPIView,
    PortalCourseLessonsAPIView,
    PortalCourseListAPIView,
    PortalMeAPIView,
)

app_name = "portal_api"

urlpatterns = [
    path("me/", PortalMeAPIView.as_view(), name="me"),
    path("courses/", PortalCourseListAPIView.as_view(), name="course-list"),
    path("courses/<uuid:course_id>/", PortalCourseDetailAPIView.as_view(), name="course-detail"),
    path("courses/<uuid:course_id>/lessons/", PortalCourseLessonsAPIView.as_view(), name="course-lessons"),
]
