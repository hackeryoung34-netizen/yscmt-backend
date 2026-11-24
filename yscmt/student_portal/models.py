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
    avatar_url = models.URLField(max_length=2048, null=True, blank=True)
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
    title = models.CharField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=80, blank=True, default="Beginner")
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
    sort_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

class PortalExam(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(PortalCourse, related_name="exams", on_delete=models.CASCADE)
    title = models.CharField(max_length=220)
    instructions = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    pass_mark = models.PositiveSmallIntegerField(default=50)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "title"]
        constraints = [
            models.CheckConstraint(condition=models.Q(duration_minutes__gt=0), name="portal_exam_duration_positive"),
            models.CheckConstraint(condition=models.Q(pass_mark__lte=100), name="portal_exam_pass_mark_max_100"),
        ]


class PortalExamQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(PortalExam, related_name="questions", on_delete=models.CASCADE)
    question_text = models.TextField()
    options = models.JSONField()
    correct_option = models.PositiveSmallIntegerField()
    sort_order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(correct_option__lte=3), name="portal_question_correct_option_0_3"),
        ]


class PortalExamSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(PortalExam, related_name="sessions", on_delete=models.PROTECT)
    student = models.ForeignKey(PortalIdentity, related_name="exam_sessions", on_delete=models.PROTECT)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "student"],
                condition=models.Q(submitted_at__isnull=True),
                name="uniq_active_portal_exam_session",
            ),
        ]


class PortalExamAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(PortalExamSession, related_name="attempt", on_delete=models.PROTECT)
    exam = models.ForeignKey(PortalExam, related_name="attempts", on_delete=models.PROTECT)
    student = models.ForeignKey(PortalIdentity, related_name="exam_attempts", on_delete=models.PROTECT)
    answers = models.JSONField(default=dict)
    score = models.PositiveSmallIntegerField(default=0)
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField()
    submitted_at = models.DateTimeField()

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(score__lte=100), name="portal_exam_attempt_score_max_100"),
        ]

class PortalPayment(models.Model):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ABANDONED = "abandoned"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SUCCESS, "Success"),
        (FAILED, "Failed"),
        (ABANDONED, "Abandoned"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(PortalEnrollment, related_name="payments", on_delete=models.PROTECT)
    student = models.ForeignKey(PortalIdentity, related_name="payments", on_delete=models.PROTECT)
    reference = models.CharField(max_length=100, unique=True)
    amount_kobo = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    authorization_url = models.URLField(max_length=2048, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment"],
                condition=models.Q(status="pending"),
                name="uniq_pending_portal_payment_per_enrollment",
            ),
            models.CheckConstraint(condition=models.Q(amount_kobo__gt=0), name="portal_payment_amount_positive"),
        ]

class PortalCertificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate_code = models.CharField(max_length=40, unique=True)
    student = models.ForeignKey(PortalIdentity, related_name="certificates", on_delete=models.PROTECT)
    course = models.ForeignKey(PortalCourse, related_name="certificates", on_delete=models.PROTECT)
    student_name = models.CharField(max_length=200)
    course_title = models.CharField(max_length=220)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "course"], name="uniq_portal_student_course_certificate"),
        ]

class PortalPracticeSubmission(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("reviewing", "Reviewing"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(PortalIdentity, related_name="practice_submissions", on_delete=models.PROTECT)
    lab_key = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    submission_text = models.TextField(blank=True)
    project_url = models.URLField(blank=True, max_length=2048)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")
    reviewer_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(PortalIdentity, related_name="practice_reviews", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-submitted_at"]


class PortalClassroomSession(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("live", "Live"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(PortalCourse, related_name="classroom_sessions", on_delete=models.CASCADE)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    meeting_url = models.URLField(max_length=2048)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    created_by = models.ForeignKey(PortalIdentity, related_name="classroom_sessions_created", null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="portal_classroom_end_after_start"),
            models.CheckConstraint(condition=models.Q(status__in=["scheduled", "live", "completed", "cancelled"]), name="portal_classroom_status_valid"),
        ]


class PortalClassroomAttendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(PortalClassroomSession, related_name="attendance", on_delete=models.CASCADE)
    student = models.ForeignKey(PortalIdentity, related_name="classroom_attendance", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "session"], name="uniq_portal_student_classroom_attendance"),
        ]


class PortalClassroomMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(PortalCourse, related_name="classroom_messages", on_delete=models.CASCADE)
    student = models.ForeignKey(PortalIdentity, related_name="classroom_messages", on_delete=models.CASCADE)
    author_role = models.CharField(max_length=20, choices=[("student", "Student"), ("instructor", "Instructor"), ("admin", "Admin")], default="student")
    message = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(author_role__in=["student", "instructor", "admin"]), name="portal_classroom_author_role_valid")]


class PortalClassroomAnnouncement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(PortalCourse, related_name="announcements", null=True, blank=True, on_delete=models.CASCADE)
    title = models.CharField(max_length=220)
    body = models.TextField()
    published = models.BooleanField(default=True)
    created_by = models.ForeignKey(PortalIdentity, related_name="classroom_announcements_created", null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PortalTeacherReply(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(PortalCourse, related_name="teacher_replies", on_delete=models.CASCADE)
    created_by = models.ForeignKey(PortalIdentity, related_name="teacher_replies", null=True, blank=True, on_delete=models.PROTECT)
    message = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

class PortalAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(PortalIdentity, related_name="audit_events", null=True, blank=True, on_delete=models.SET_NULL)
    actor_handle = models.CharField(max_length=255, blank=True, default="")
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"], name="portal_audit_target_idx"),
            models.Index(fields=["created_at"], name="portal_audit_created_idx"),
        ]

class PortalCourseInstructor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(PortalCourse, related_name="instructor_assignments", on_delete=models.CASCADE)
    instructor = models.ForeignKey(PortalIdentity, related_name="course_assignments", on_delete=models.PROTECT)
    assigned_by = models.ForeignKey(PortalIdentity, related_name="instructor_assignments_made", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["course", "instructor"], name="uniq_portal_course_instructor"),
        ]
        ordering = ["course__title", "instructor__username"]


class PortalPaymentSubmission(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UPLOADING = "uploading"
    STATUS_CHOICES = [(UPLOADING, "Uploading"), (PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(PortalEnrollment, related_name="bank_payment_submissions", on_delete=models.PROTECT)
    student = models.ForeignKey(PortalIdentity, related_name="bank_payment_submissions", on_delete=models.PROTECT)
    course = models.ForeignKey(PortalCourse, related_name="bank_payment_submissions", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    transfer_reference = models.CharField(max_length=120, blank=True)
    storage_key = models.CharField(max_length=512, unique=True)
    content_type = models.CharField(max_length=100)
    file_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    admin_note = models.CharField(max_length=2000, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    upload_expires_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(PortalIdentity, related_name="bank_payment_reviews", null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [models.Index(fields=["status", "submitted_at"], name="portal_bank_status_idx")]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="portal_bank_amount_nonnegative"),
            models.UniqueConstraint(fields=["enrollment"], condition=models.Q(status__in=["uploading", "pending"]), name="uniq_active_bank_payment_submission"),
        ]

class PortalLegacyUserMap(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("linked", "Linked"),
        ("verified", "Verified"),
        ("needs_review", "Needs review"),
    ]
    source_system = models.CharField(max_length=50, default="hatchable")
    legacy_user_id = models.CharField(max_length=255)
    identity = models.ForeignKey(PortalIdentity, related_name="legacy_user_mappings", on_delete=models.PROTECT)
    migration_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source_system", "legacy_user_id"], name="uniq_portal_legacy_source_user"),
            models.UniqueConstraint(fields=["source_system", "identity"], name="uniq_portal_legacy_source_identity"),
        ]
        indexes = [models.Index(fields=["identity"], name="portal_legacy_identity_idx")]
        db_table = '"private"."legacy_user_map"'


class PortalSiteSetting(models.Model):
    setting_key = models.CharField(max_length=255, primary_key=True)
    setting_value = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"private"."site_settings"'
