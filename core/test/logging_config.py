# core/tests/__init__.py
"""
Тесты для core приложения
"""

from .test_logging import LoggingTestCase
from .test_middleware import MiddlewareTestCase

__all__ = [
    'LoggingTestCase',
    'MiddlewareTestCase',
]