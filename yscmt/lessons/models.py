from django.db import models
from courses.models import Course


class Lesson(models.Model):

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lessons"
    )

    title = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    video_url = models.URLField(
        blank=True,
        null=True
    )

    content = models.TextField(
        blank=True
    )

    resource = models.FileField(
        upload_to="lesson_resources/",
        blank=True,
        null=True
    )

    order = models.PositiveIntegerField(
        default=1
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title
