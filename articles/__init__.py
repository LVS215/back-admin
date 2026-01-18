# articles/__init__.py
"""
Приложение для управления статьями и категориями
"""

default_app_config = 'articles.apps.ArticlesConfig'

# Экспорт основных моделей
from .models import Article, Category

__all__ = ['Article', 'Category']