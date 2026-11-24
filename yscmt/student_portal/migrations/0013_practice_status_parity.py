from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("student_portal", "0012_password_reset_tokens")]
    operations = [
        migrations.AlterField(
            model_name="portalpracticesubmission",
            name="status",
            field=models.CharField(
                choices=[("submitted", "Submitted"), ("in_review", "In review"), ("approved", "Approved"), ("needs_changes", "Needs changes")],
                default="submitted", max_length=20,
            ),
        ),
    ]
