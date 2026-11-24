import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("student_portal", "0004_portal_certificate"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalPracticeSubmission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("lab_key", models.CharField(max_length=100)),
                ("title", models.CharField(max_length=200)),
                ("submission_text", models.TextField(blank=True)),
                ("project_url", models.URLField(blank=True, max_length=2048)),
                ("status", models.CharField(choices=[("submitted", "Submitted"), ("reviewing", "Reviewing"), ("approved", "Approved"), ("rejected", "Rejected")], default="submitted", max_length=20)),
                ("reviewer_notes", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="practice_submissions", to="student_portal.portalidentity")),
            ],
            options={"ordering": ["-submitted_at"]},
        ),
        migrations.CreateModel(
            name="PortalClassroomSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("meeting_url", models.URLField(max_length=2048)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("status", models.CharField(choices=[("scheduled", "Scheduled"), ("live", "Live"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="scheduled", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="classroom_sessions", to="student_portal.portalcourse")),
            ],
            options={"ordering": ["-starts_at"]},
        ),
        migrations.CreateModel(
            name="PortalClassroomAttendance",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance", to="student_portal.portalclassroomsession")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="classroom_attendance", to="student_portal.portalidentity")),
            ],
        ),
        migrations.CreateModel(
            name="PortalClassroomMessage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("author_role", models.CharField(default="student", max_length=20)),
                ("message", models.CharField(max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="classroom_messages", to="student_portal.portalcourse")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="classroom_messages", to="student_portal.portalidentity")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="PortalClassroomAnnouncement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("body", models.TextField()),
                ("published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("course", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="announcements", to="student_portal.portalcourse")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PortalTeacherReply",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("message", models.CharField(max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_replies", to="student_portal.portalcourse")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="teacher_replies", to="student_portal.portalidentity")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="portalclassroomsession",
            constraint=models.CheckConstraint(condition=models.Q(("ends_at__gt", models.F("starts_at"))), name="portal_classroom_end_after_start"),
        ),
        migrations.AddConstraint(
            model_name="portalclassroomattendance",
            constraint=models.UniqueConstraint(fields=("student", "session"), name="uniq_portal_student_classroom_attendance"),
        ),
    ]
