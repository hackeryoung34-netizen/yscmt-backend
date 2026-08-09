from django.db import models
from django.contrib.auth.models import User



class Profile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True
    )


    def __str__(self):
        return self.user.username




class Message(models.Model):

    name = models.CharField(
        max_length=100
    )

    email = models.EmailField()

    message = models.TextField()


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):
        return self.name
