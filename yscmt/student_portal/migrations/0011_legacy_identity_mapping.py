import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("student_portal", "0010_source_schema_parity")]
    operations = [
        migrations.AddField(
            model_name="portalidentity",
            name="avatar_url",
            field=models.URLField(blank=True, max_length=2048, null=True),
        ),
        migrations.CreateModel(
            name="PortalLegacyUserMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_system", models.CharField(default="hatchable", max_length=50)),
                ("legacy_user_id", models.CharField(max_length=255)),
                ("migration_status", models.CharField(choices=[("pending", "Pending"), ("linked", "Linked"), ("verified", "Verified"), ("needs_review", "Needs review")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("identity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="legacy_user_mappings", to="student_portal.portalidentity")),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("source_system", "legacy_user_id"), name="uniq_portal_legacy_source_user"),
                models.UniqueConstraint(fields=("source_system", "identity"), name="uniq_portal_legacy_source_identity"),
            ]},
        ),
        migrations.AddIndex(
            model_name="portallegacyusermap",
            index=models.Index(fields=["identity"], name="portal_legacy_identity_idx"),
        ),
        migrations.CreateModel(
            name="PortalSiteSetting",
            fields=[
                ("setting_key", models.CharField(max_length=255, primary_key=True, serialize=False)),
                ("setting_value", models.JSONField(default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "student_portal_site_settings"},
        ),
    ]
