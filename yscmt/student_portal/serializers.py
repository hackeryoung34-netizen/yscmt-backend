from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import PortalIdentity, PortalCourse, PortalLesson, PortalEnrollment

class PortalRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate_username(self, value):
        value = value.strip()
        if PortalIdentity.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already registered.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if PortalIdentity.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        identity = PortalIdentity(
            username=validated_data["username"],
            email=validated_data["email"],
            full_name=validated_data.get("full_name", ""),
            role=PortalIdentity.ROLE_STUDENT,
        )
        identity.set_password(validated_data["password"])
        identity.save()
        return identity


class PortalTokenSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs["username"].strip()
        identity = PortalIdentity.objects.filter(username__iexact=username, is_active=True).first()
        if not identity or not identity.check_password(attrs["password"]):
            raise serializers.ValidationError({"detail": "Invalid username or password."})
        refresh = RefreshToken()
        refresh["portal_identity_id"] = str(identity.pk)
        refresh["role"] = identity.role
        refresh["token_type"] = "refresh"
        access = refresh.access_token
        access["portal_identity_id"] = str(identity.pk)
        access["role"] = identity.role
        return {"refresh": str(refresh), "access": str(access)}


class PortalCourseSerializer(serializers.ModelSerializer):
    enrollment_status = serializers.SerializerMethodField()

    class Meta:
        model = PortalCourse
        fields = ["id", "title", "description", "level", "fee_amount", "fee_currency", "enrollment_status"]

    def get_enrollment_status(self, obj):
        identity = self.context["request"].user
        enrollment = PortalEnrollment.objects.filter(student=identity, course=obj).first()
        return enrollment.status if enrollment else None


class PortalLessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortalLesson
        fields = ["id", "title", "content", "video_url", "sort_order"]

class PortalEnrollmentCreateSerializer(serializers.Serializer):
    course_id = serializers.UUIDField()

class PortalExamSubmitSerializer(serializers.Serializer):
    answers = serializers.DictField(
        child=serializers.IntegerField(min_value=0, max_value=3),
        allow_empty=False,
    )

    def validate_answers(self, value):
        import uuid
        if len(value) > 100:
            raise serializers.ValidationError("An exam cannot contain more than 100 answers.")
        normalized = {}
        for question_id, option_index in value.items():
            try:
                normalized[str(uuid.UUID(question_id))] = option_index
            except (ValueError, TypeError, AttributeError):
                raise serializers.ValidationError("Every answer key must be a valid question UUID.")
        return normalized

class PortalPracticeSubmitSerializer(serializers.Serializer):
    lab_key = serializers.CharField(min_length=1, max_length=100)
    title = serializers.CharField(min_length=1, max_length=200)
    submission_text = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    project_url = serializers.CharField(required=False, allow_blank=True, max_length=2048)

    def validate_project_url(self, value):
        value = value.strip()
        if value and not value.startswith("https://"):
            raise serializers.ValidationError("Project links must use HTTPS.")
        return value


class PortalClassroomMessageSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1, max_length=2000)
