import uuid
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("student_portal", "0005_classroom_practice")]
    operations = [
        migrations.CreateModel(
            name="PortalAuditLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=80)),
                ("target_type", models.CharField(max_length=80)),
                ("target_id", models.CharField(max_length=80)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="student_portal.portalidentity")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="portalauditlog", index=models.Index(fields=["target_type", "target_id"], name="portal_audit_target_idx")),
        migrations.AddIndex(model_name="portalauditlog", index=models.Index(fields=["created_at"], name="portal_audit_created_idx")),
    ]
}
