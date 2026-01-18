# users/tests/__init__.py
"""
Тесты для приложения users
"""

from .test_models import UserModelTestCase, TokenModelTestCase
from .test_auth import AuthAPITestCase
from .test_users import UserAPITestCase

__all__ = [
    'UserModelTestCase',
    'TokenModelTestCase',
    'AuthAPITestCase',
    'UserAPITestCase',
]