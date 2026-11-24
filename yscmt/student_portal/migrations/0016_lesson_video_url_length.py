from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("student_portal", "0015_classroom_author_role_parity")]
    operations = [
        migrations.AlterField(
            model_name="portallesson",
            name="video_url",
            field=models.URLField(blank=True, max_length=1000),
        ),
    ]
