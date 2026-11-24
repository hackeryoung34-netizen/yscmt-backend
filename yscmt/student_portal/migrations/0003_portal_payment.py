import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("student_portal", "0002_portal_exams"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalPayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reference", models.CharField(max_length=100, unique=True)),
                ("amount_kobo", models.PositiveBigIntegerField()),
                ("currency", models.CharField(default="NGN", max_length=3)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed"), ("abandoned", "Abandoned")], default="pending", max_length=20)),
                ("authorization_url", models.URLField(blank=True, max_length=2048)),
                ("gateway_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="student_portal.portalenrollment")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="student_portal.portalidentity")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="portalpayment",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("enrollment",), name="uniq_pending_portal_payment_per_enrollment"),
        ),
        migrations.AddConstraint(
            model_name="portalpayment",
            constraint=models.CheckConstraint(condition=models.Q(("amount_kobo__gt", 0)), name="portal_payment_amount_positive"),
        ),
    ]
