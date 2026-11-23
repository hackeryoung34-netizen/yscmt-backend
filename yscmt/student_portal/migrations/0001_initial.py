import uuid
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="PortalIdentity",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("username", models.CharField(max_length=150, unique=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("password", models.CharField(max_length=128)),
                ("full_name", models.CharField(blank=True, max_length=200)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("role", models.CharField(choices=[("student", "Student"), ("instructor", "Instructor"), ("admin", "Admin")], default="student", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="PortalCourse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("level", models.CharField(blank=True, max_length=80)),
                ("fee_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("fee_currency", models.CharField(default="NGN", max_length=3)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["title"]},
        ),
        migrations.CreateModel(
            name="PortalLesson",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("content", models.TextField(blank=True)),
                ("video_url", models.URLField(blank=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lessons", to="student_portal.portalcourse")),
            ],
            options={"ordering": ["sort_order", "created_at"]},
        ),
        migrations.CreateModel(
            name="PortalEnrollment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("completed", "Completed"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="student_portal.portacourse")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="student_portal.portalidentity")),
            ],
        ),
        migrations.CreateModel(
            name="PortalLessonProgress",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("lesson", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="progress_records", to="student_portal.portallesson")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lesson_progress", to="student_portal.portalidentity")),
            ],
        ),
        migrations.AddConstraint(model_name="portalenrollment", constraint=models.UniqueConstraint(fields=("student", "course"), name="uniq_portal_student_course")),
        migrations.AddConstraint(model_name="portallessonprogress", constraint=models.UniqueConstraint(fields=("student", "lesson"), name="uniq_portal_student_lesson_progress")),
    ]
