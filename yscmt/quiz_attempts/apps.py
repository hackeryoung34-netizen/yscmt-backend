from django.apps import AppConfig


class QuizAttemptsConfig(AppConfig):

    default_auto_field = "django.db.models.BigAutoField"
    name = "quiz_attempts"


    def ready(self):
        import quiz_attempts.signals
