import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("student_portal", "0003_portal_payment"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalCertificate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("certificate_code", models.CharField(max_length=40, unique=True)),
                ("student_name", models.CharField(max_length=200)),
                ("course_title", models.CharField(max_length=220)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="certificates", to="student_portal.portalcourse")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="certificates", to="student_portal.portalidentity")),
            ],
            options={"ordering": ["-issued_at"]},
        ),
        migrations.AddConstraint(
            model_name="portalcertificate",
            constraint=models.UniqueConstraint(fields=("student", "course"), name="uniq_portal_student_course_certificate"),
        ),
    ]
