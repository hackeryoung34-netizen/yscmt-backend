from rest_framework import serializers

class RecentCourseSerializer(serializers.Serializer):
    course__name = serializers.CharField()
    enrolled_at = serializers.DateTimeField()
