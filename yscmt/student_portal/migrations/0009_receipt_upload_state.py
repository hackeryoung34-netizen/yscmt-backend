from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("student_portal", "0008_portal_payment_submission")]
    operations = [
        migrations.AlterField(
            model_name="portalpaymentsubmission",
            name="status",
            field=models.CharField(
                choices=[("uploading", "Uploading"), ("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                default="pending", max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="portalpaymentsubmission",
            name="upload_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="portalpaymentsubmission",
            constraint=models.UniqueConstraint(
                fields=("enrollment",),
                condition=models.Q(("status__in", ["uploading", "pending"])),
                name="uniq_active_bank_payment_submission",
            ),
        ),
    ]
