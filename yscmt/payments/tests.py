from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from courses.models import Course
from payments.models import Payment


class CreatePaymentAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student",
            password="StrongTestPass123!"
        )
        self.course = Course.objects.create(
            name="Paid course",
            description="Test course",
            price="100.00"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_creates_pending_payment_for_paid_course(self):
        response = self.client.post(
            "/api/payments/create/",
            {"course": self.course.pk, "payment_method": "paystack"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Payment.objects.get().student, self.user)

    def test_rejects_payment_for_free_course(self):
        free_course = Course.objects.create(
            name="Free course",
            description="No payment required",
            price="0.00"
        )
        response = self.client.post(
            "/api/payments/create/",
            {"course": free_course.pk, "payment_method": "paystack"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)

    def test_rejects_unknown_payment_method(self):
        response = self.client.post(
            "/api/payments/create/",
            {"course": self.course.pk, "payment_method": "unknown"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)
