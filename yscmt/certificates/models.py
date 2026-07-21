from django.db import models
from django.contrib.auth.models import User
from courses.models import Course


class Certificate(models.Model):
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="certificates"
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="certificates"
    )

    certificate_number = models.CharField(
        max_length=100,
        unique=True
    )

    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.certificate_number
