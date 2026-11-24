from django.urls import path
from .views import (
    PortalRegisterAPIView, PortalTokenObtainPairView, PortalMeAPIView,
    PortalCourseListAPIView, PortalCourseDetailAPIView,
    PortalCourseLessonsAPIView, PortalEnrollmentCreateAPIView,
    PortalLessonCompleteAPIView, PortalCourseProgressAPIView,
    PortalCourseExamsAPIView, PortalExamStartAPIView,
    PortalExamQuestionsAPIView, PortalExamSubmitAPIView,
)

urlpatterns = [
    path("auth/register/", PortalRegisterAPIView.as_view(), name="portal-register"),
    path("token/", PortalTokenObtainPairView.as_view(), name="portal-token"),
    path("me/", PortalMeAPIView.as_view(), name="portal-me"),
    path("courses/", PortalCourseListAPIView.as_view(), name="portal-courses"),
    path("courses/<uuid:course_id>/", PortalCourseDetailAPIView.as_view(), name="portal-course-detail"),
    path("courses/<uuid:course_id>/lessons/", PortalCourseLessonsAPIView.as_view(), name="portal-course-lessons"),
    path("enrollments/", PortalEnrollmentCreateAPIView.as_view(), name="portal-enrollment-create"),
    path("lessons/<uuid:lesson_id>/complete/", PortalLessonCompleteAPIView.as_view(), name="portal-lesson-complete"),
    path("courses/<uuid:course_id>/progress/", PortalCourseProgressAPIView.as_view(), name="portal-course-progress"),
    path("courses/<uuid:course_id>/exams/", PortalCourseExamsAPIView.as_view(), name="portal-course-exams"),
    path("exams/<uuid:exam_id>/start/", PortalExamStartAPIView.as_view(), name="portal-exam-start"),
    path("exam-sessions/<uuid:session_id>/questions/", PortalExamQuestionsAPIView.as_view(), name="portal-exam-questions"),
    path("exam-sessions/<uuid:session_id>/submit/", PortalExamSubmitAPIView.as_view(), name="portal-exam-submit"),
]
