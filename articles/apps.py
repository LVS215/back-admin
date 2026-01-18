# articles/apps.py
from django.apps import AppConfig

class ArticlesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'articles'
    verbose_name = 'Articles'
    
    def ready(self):
        # Импортируем сигналы, если они есть
        try:
            import articles.signals  # noqa: F401
        except ImportError:
            pass