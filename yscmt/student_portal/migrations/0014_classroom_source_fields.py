from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("student_portal", "0013_practice_status_parity")]
    operations = [
        migrations.AddField(
            model_name="portalclassroomsession",
            name="created_by_handle",
            field=models.CharField(blank=True, default="admin", max_length=255),
        ),
        migrations.AddField(
            model_name="portalclassroomannouncement",
            name="created_by_handle",
            field=models.CharField(blank=True, default="admin", max_length=255),
        ),
        migrations.AddField(
            model_name="portalteacherreply",
            name="created_by_handle",
            field=models.CharField(blank=True, default="admin", max_length=255),
        ),
        migrations.AlterField(
            model_name="portalclassroommessage",
            name="message",
            field=models.CharField(max_length=3000),
        ),
        migrations.AlterField(
            model_name="portalteacherreply",
            name="message",
            field=models.CharField(max_length=3000),
        ),
    ]
