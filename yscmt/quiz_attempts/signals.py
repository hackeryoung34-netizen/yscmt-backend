from django.db.models.signals import post_save
from django.dispatch import receiver
from uuid import uuid4

from .models import QuizAttempt
from certificates.models import Certificate


@receiver(post_save, sender=QuizAttempt)
def create_certificate(sender, instance, created, **kwargs):

    if instance.completed and instance.score >= 50:

        Certificate.objects.get_or_create(
            student=instance.student,
            course=instance.quiz.course,
            defaults={
                "certificate_number": 
                f"YSCMT-{uuid4().hex[:8].upper()}"
            }
        )
