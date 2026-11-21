from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from courses.models import Course
from enrollments.models import Enrollment
from lessons.models import Lesson


class LessonAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student",
            password="StrongTestPass123!"
        )
        self.course = Course.objects.create(
            name="Course",
            description="Test course",
            price="50.00"
        )
        self.lesson = Lesson.objects.create(
            course=self.course,
            title="Private lesson",
            content="Restricted course material",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_blocks_lesson_for_non_enrolled_student(self):
        response = self.client.get(f"/api/lessons/{self.lesson.pk}/")

        self.assertEqual(response.status_code, 404)

    def test_allows_lesson_for_enrolled_student(self):
        Enrollment.objects.create(
            student=self.user,
            course=self.course,
        )
        response = self.client.get(f"/api/lessons/{self.lesson.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["content"], "Restricted course material")
