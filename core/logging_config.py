import structlog
import logging
from django.utils import timezone
from django.contrib.auth import get_user_model

def get_user_info(request):
    """Получение информации о пользователе из запроса"""
    if hasattr(request, 'auth') and request.auth:
        return {
            'user_id': str(request.auth.id),
            'username': request.auth.username,
        }
    return {'user_id': None, 'username': 'anonymous'}

def add_request_context(request, logger, method_name, event_dict):
    """Добавление контекста запроса в логи"""
    event_dict['timestamp'] = timezone.now().isoformat()
    event_dict['method'] = request.method
    event_dict['path'] = request.path
    event_dict['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
    event_dict['ip_address'] = request.META.get('REMOTE_ADDR', '')
    
    user_info = get_user_info(request)
    event_dict.update(user_info)
    
    return event_dict

class LoggingMiddleware:
    """Middleware для логирования запросов"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = structlog.get_logger(__name__)
    
    def __call__(self, request):
        # Логирование входящего запроса
        self.logger.info(
            "request_started",
            method=request.method,
            path=request.path,
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
        )
        
        response = self.get_response(request)
        
        # Логирование ответа
        self.logger.info(
            "request_completed",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            content_length=len(response.content) if hasattr(response, 'content') else 0,
        )
        
        return response