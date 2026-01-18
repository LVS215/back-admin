import logging
import logging.config
import os

def setup_logging():
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'simple'
            },
            'file': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join('logs', 'error.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'formatter': 'verbose',
            },
            'security_file': {
                'level': 'WARNING',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join('logs', 'security.log'),
                'maxBytes': 10485760,
                'backupCount': 5,
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django.security': {
                'handlers': ['security_file'],
                'level': 'WARNING',
                'propagate': False,
            },
            'core': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    })
