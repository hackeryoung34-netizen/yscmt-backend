from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User


class Course(models.Model):

    name=models.CharField(
        max_length=100
    )


    description=models.TextField()


    def __str__(self):

        return self.name



class Enrollment(models.Model):

    student=models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )


    course=models.ForeignKey(
        Course,
        on_delete=models.CASCADE
    )


    date=models.DateTimeField(
        auto_now_add=True
    )