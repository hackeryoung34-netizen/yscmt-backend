import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("student_portal", "0011_legacy_identity_mapping")]
    operations = [
        migrations.AddField(
            model_name="portalidentity",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalidentity",
            name="must_reset_password",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="PortalPasswordResetToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("identity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="password_reset_tokens", to="student_portal.portalidentity")),
            ],
        ),
        migrations.AddIndex(
            model_name="portalpasswordresettoken",
            index=models.Index(fields=["identity", "created_at"], name="portal_pwd_identity_idx"),
        ),
        migrations.AddIndex(
            model_name="portalpasswordresettoken",
            index=models.Index(fields=["expires_at", "used_at"], name="portal_pwd_expiry_idx"),
        ),
    ]
