import uuid
from django.db import models
from django.contrib.auth.hashers import make_password, check_password

class PortalIdentity(models.Model):
    ROLE_STUDENT = "student"
    ROLE_INSTRUCTOR = "instructor"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [(ROLE_STUDENT, "Student"), (ROLE_INSTRUCTOR, "Instructor"), (ROLE_ADMIN, "Admin")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.username


class PortalCourse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=80, blank=True)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fee_currency = models.CharField(max_length=3, default="NGN")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]


class PortalLesson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(PortalCourse, related_name="lessons", on_delete=models.CASCADE)
    title = models.CharField(max_length=220)
    content = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "created_at"]


class PortalEnrollment(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    COMPLETED = "completed"
    REJECTED = "rejected"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (COMPLETED, "Completed"), (REJECTED, "Rejected")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(PortalIdentity, related_name="enrollments", on_delete=models.PROTECT)
    course = models.ForeignKey(PortalCourse, related_name="enrollments", on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "course"], name="uniq_portal_student_course")]
        ordering = ["-created_at"]


class PortalLessonProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(PortalIdentity, related_name="lesson_progress", on_delete=models.CASCADE)
    lesson = models.ForeignKey(PortalLesson, related_name="progress_records", on_delete=models.CASCADE)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "lesson"], name="uniq_portal_student_lesson_progress")]
