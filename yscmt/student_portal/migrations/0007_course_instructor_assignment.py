import uuid
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("student_portal", "0006_portal_audit_log")]
    operations = [
        migrations.CreateModel(
            name="PortalCourseInstructor",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="instructor_assignments_made", to="student_portal.portalidentity")),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="instructor_assignments", to="student_portal.portalcourse")),
                ("instructor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="course_assignments", to="student_portal.portalidentity")),
            ],
            options={"ordering": ["course__title", "instructor__username"]},
        ),
        migrations.AddConstraint(model_name="portalcourseinstructor", constraint=models.UniqueConstraint(fields=("course", "instructor"), name="uniq_portal_course_instructor")),
    ]
