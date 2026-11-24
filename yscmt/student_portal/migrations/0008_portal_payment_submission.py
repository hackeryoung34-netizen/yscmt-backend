
import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [("student_portal", "0007_course_instructor_assignment")]
    operations = [
        migrations.CreateModel(
            name="PortalPaymentSubmission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="NGN", max_length=3)),
                ("transfer_reference", models.CharField(blank=True, max_length=120)),
                ("storage_key", models.CharField(max_length=512, unique=True)),
                ("content_type", models.CharField(max_length=100)),
                ("file_name", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("admin_note", models.CharField(blank=True, max_length=2000)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bank_payment_submissions", to="student_portal.portalcourse")),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bank_payment_submissions", to="student_portal.portalenrollment")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bank_payment_reviews", to="student_portal.portalidentity")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bank_payment_submissions", to="student_portal.portalidentity")),
            ],
            options={"ordering": ["-submitted_at"]},
        ),
        migrations.AddIndex(model_name="portalpaymentsubmission", index=models.Index(fields=["status", "submitted_at"], name="portal_bank_status_idx")),
        migrations.AddConstraint(model_name="portalpaymentsubmission", constraint=models.CheckConstraint(condition=models.Q(("amount__gte", 0)), name="portal_bank_amount_nonnegative")),
    ]
