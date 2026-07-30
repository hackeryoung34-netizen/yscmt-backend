from django.db import models
from django.conf import settings
from courses.models import Course


class Payment(models.Model):

    PAYMENT_METHODS = [
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("paystack", "Paystack"),
        ("flutterwave", "Flutterwave"),
        ("bank", "Bank Transfer"),
    ]

    STATUS = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHODS
    )

    transaction_id = models.CharField(
        max_length=200,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.student.username} - {self.course.name}"
