# users/__init__.py
"""
Приложение для управления пользователями и аутентификацией
"""

default_app_config = 'users.apps.UsersConfig'

# Экспорт основных моделей
from .models import User, Token

__all__ = ['User', 'Token']