# comments/apps.py
from django.apps import AppConfig

class CommentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'comments'
    verbose_name = 'Comments'
    
    def ready(self):
        # Импортируем сигналы, если они есть
        try:
            import comments.signals  # noqa: F401
        except ImportError:
            pass