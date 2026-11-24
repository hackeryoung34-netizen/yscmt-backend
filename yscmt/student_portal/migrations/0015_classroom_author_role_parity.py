from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("student_portal", "0014_classroom_source_fields")]
    operations = [
        migrations.AlterField(
            model_name="portalclassroommessage",
            name="author_role",
            field=models.CharField(
                choices=[("student", "Student"), ("teacher", "Teacher")],
                default="student", max_length=20,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="portalclassroommessage",
            name="portal_classroom_author_role_valid",
        ),
        migrations.AddConstraint(
            model_name="portalclassroommessage",
            constraint=models.CheckConstraint(
                condition=models.Q(("author_role__in", ["student", "teacher"])),
                name="portal_classroom_author_role_valid",
            ),
        ),
    ]
