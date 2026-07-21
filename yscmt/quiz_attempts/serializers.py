from rest_framework import serializers
from .models import QuizAttempt


class QuizAttemptSerializer(serializers.ModelSerializer):

    class Meta:
        model = QuizAttempt
        fields = "__all__"
