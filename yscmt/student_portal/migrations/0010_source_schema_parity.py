import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("student_portal", "0009_receipt_upload_state")]
    operations = [
        migrations.AlterField(
            model_name="portalcourse",
            name="title",
            field=models.CharField(max_length=220, unique=True),
        ),
        migrations.AddField(
            model_name="portallesson",
            name="updated_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="portalpracticesubmission",
            name="reviewed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="practice_reviews", to="student_portal.portalidentity"),
        ),
        migrations.AddField(
            model_name="portalclassroomsession",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="classroom_sessions_created", to="student_portal.portalidentity"),
        ),
        migrations.AddConstraint(
            model_name="portalclassroomsession",
            constraint=models.CheckConstraint(condition=models.Q(("status__in", ["scheduled", "live", "completed", "cancelled"])), name="portal_classroom_status_valid"),
        ),
        migrations.AlterField(
            model_name="portalclassroommessage",
            name="author_role",
            field=models.CharField(choices=[("student", "Student"), ("instructor", "Instructor"), ("admin", "Admin")], default="student", max_length=20),
        ),
        migrations.AddConstraint(
            model_name="portalclassroommessage",
            constraint=models.CheckConstraint(condition=models.Q(("author_role__in", ["student", "instructor", "admin"])), name="portal_classroom_author_role_valid"),
        ),
        migrations.AddField(
            model_name="portalclassroomannouncement",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="classroom_announcements_created", to="student_portal.portalidentity"),
        ),
        migrations.AlterField(
            model_name="portalteacherreply",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="teacher_replies", to="student_portal.portalidentity"),
        ),
        migrations.AlterField(
            model_name="portalauditlog",
            name="actor",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to="student_portal.portalidentity"),
        ),
        migrations.AddField(
            model_name="portalauditlog",
            name="legacy_id",
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="portalauditlog",
            name="actor_handle",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="portalauditlog",
            name="target_id",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AlterField(
            model_name="portallesson",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
