from django.apps import AppConfig


class YscmtConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "yscmt"

    def ready(self):
        import yscmt.admin
