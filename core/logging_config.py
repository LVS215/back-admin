import logging
import logging.config
import os
from django.utils import timezone

def setup_logging():
    """Настройка логирования для проекта"""
    
    # Создаем директорию для логов
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {asctime} {message}',
                'style': '{',
            },
            'json': {
                'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s", "user": "%(user)s", "ip": "%(ip)s"}',
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
            },
            'file_info': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'info.log'),
                'maxBytes': 10485760,  # 10 MB
                'backupCount': 10,
                'formatter': 'verbose',
            },
            'file_error': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'error.log'),
                'maxBytes': 10485760,
                'backupCount': 10,
                'formatter': 'verbose',
            },
            'file_security': {
                'level': 'WARNING',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'security.log'),
                'maxBytes': 10485760,
                'backupCount': 10,
                'formatter': 'verbose',
            },
            'file_audit': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'audit.log'),
                'maxBytes': 10485760,
                'backupCount': 10,
                'formatter': 'json',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'api': {
                'handlers': ['console', 'file_info', 'file_audit'],
                'level': 'INFO',
                'propagate': False,
            },
            'core': {
                'handlers': ['console', 'file_info'],
                'level': 'INFO',
                'propagate': False,
            },
            'security': {
                'handlers': ['file_security', 'console'],
                'level': 'WARNING',
                'propagate': False,
            },
        },
        'root': {
           
