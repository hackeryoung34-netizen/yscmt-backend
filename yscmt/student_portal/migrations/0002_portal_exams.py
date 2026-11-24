import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("student_portal", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalExam",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("instructions", models.TextField(blank=True)),
                ("duration_minutes", models.PositiveSmallIntegerField(default=30)),
                ("pass_mark", models.PositiveSmallIntegerField(default=50)),
                ("is_active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exams", to="student_portal.portalcourse")),
            ],
            options={"ordering": ["created_at", "title"]},
        ),
        migrations.CreateModel(
            name="PortalExamQuestion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("question_text", models.TextField()),
                ("options", models.JSONField()),
                ("correct_option", models.PositiveSmallIntegerField()),
                ("sort_order", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("exam", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="student_portal.portalexam")),
            ],
            options={"ordering": ["sort_order", "created_at"]},
        ),
        migrations.CreateModel(
            name="PortalExamSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("exam", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sessions", to="student_portal.portalexam")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_sessions", to="student_portal.portalidentity")),
            ],
        ),
        migrations.CreateModel(
            name="PortalExamAttempt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("answers", models.JSONField(default=dict)),
                ("score", models.PositiveSmallIntegerField(default=0)),
                ("passed", models.BooleanField(default=False)),
                ("started_at", models.DateTimeField()),
                ("submitted_at", models.DateTimeField()),
                ("exam", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attempts", to="student_portal.portalexam")),
                ("session", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="attempt", to="student_portal.portalexamsession")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_attempts", to="student_portal.portalidentity")),
            ],
            options={"ordering": ["-submitted_at"]},
        ),
        migrations.AddConstraint(
            model_name="portalexam",
            constraint=models.CheckConstraint(condition=models.Q(("duration_minutes__gt", 0)), name="portal_exam_duration_positive"),
        ),
        migrations.AddConstraint(
            model_name="portalexam",
            constraint=models.CheckConstraint(condition=models.Q(("pass_mark__lte", 100)), name="portal_exam_pass_mark_max_100"),
        ),
        migrations.AddConstraint(
            model_name="portalexamquestion",
            constraint=models.CheckConstraint(condition=models.Q(("correct_option__lte", 3)), name="portal_question_correct_option_0_3"),
        ),
        migrations.AddConstraint(
            model_name="portalexamsession",
            constraint=models.UniqueConstraint(condition=models.Q(("submitted_at__isnull", True)), fields=("exam", "student"), name="uniq_active_portal_exam_session"),
        ),
        migrations.AddConstraint(
            model_name="portalexamattempt",
            constraint=models.CheckConstraint(condition=models.Q(("score__lte", 100)), name="portal_exam_attempt_score_max_100"),
        ),
    ]
