# comments/__init__.py
"""
Приложение для управления комментариями
"""

default_app_config = 'comments.apps.CommentsConfig'

# Экспорт основных моделей
from .models import Comment

__all__ = ['Comment']