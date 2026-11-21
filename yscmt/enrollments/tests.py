from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from courses.models import Course
from enrollments.models import Enrollment
from payments.models import Payment


class EnrollmentPaymentGateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student",
            password="StrongTestPass123!"
        )
        self.paid_course = Course.objects.create(
            name="Paid course",
            description="Test course",
            price="100.00"
        )
        self.free_course = Course.objects.create(
            name="Free course",
            description="Test course",
            price="0.00"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_blocks_enrollment_without_confirmed_payment(self):
        response = self.client.post(
            "/api/enrollments/",
            {"course": self.paid_course.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Enrollment.objects.count(), 0)

    def test_allows_enrollment_after_payment_is_marked_paid(self):
        Payment.objects.create(
            student=self.user,
            course=self.paid_course,
            amount=self.paid_course.price,
            payment_method="paystack",
            status="paid",
        )
        response = self.client.post(
            "/api/enrollments/",
            {"course": self.paid_course.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_allows_free_course_enrollment(self):
        response = self.client.post(
            "/api/enrollments/",
            {"course": self.free_course.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Enrollment.objects.count(), 1)
