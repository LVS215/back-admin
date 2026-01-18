# core/__init__.py
"""
Основное приложение с утилитами, middleware и общими функциями
"""

default_app_config = 'core.apps.CoreConfig'

# Экспорт middleware
from .middleware import LoggingMiddleware
from .logging_config import add_request_context, get_user_info

__all__ = [
    'LoggingMiddleware',
    'add_request_context',
    'get_user_info'
]

# Настройка structlog
import structlog
import logging

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.render_to_log_kwargs,
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)