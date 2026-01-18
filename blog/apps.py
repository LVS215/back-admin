# blog/apps.py
from django.apps import AppConfig

class BlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blog'
    verbose_name = 'Blog Application'
    
    def ready(self):
        # Импортируем сигналы, если они есть
        try:
            import blog.signals  # noqa: F401
        except ImportError:
            pass