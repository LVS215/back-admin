"""
Middleware для логирования всех операций
Требование: Логирование входа/выхода пользователя, CRUD операций
"""
import time
import json
import logging
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)
crud_logger = logging.getLogger('crud')
security_logger = logging.getLogger('security')

class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware для логирования всех HTTP запросов"""
    
    def process_request(self, request):
        request.start_time = time.time()
        request.request_id = str(timezone.now().timestamp())
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            # Информация о пользователе
            user = request.user if hasattr(request, 'user') else AnonymousUser()
            username = user.username if not isinstance(user, AnonymousUser) else 'anonymous'
            user_id = user.id if not isinstance(user, AnonymousUser) else None
            
            # Информация о запросе
            log_data = {
                'timestamp': timezone.now().isoformat(),
                'request_id': getattr(request, 'request_id', 'unknown'),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': round(duration * 1000, 2),
                'user_id': user_id,
                'username': username,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'query_params': dict(request.GET),
            }
            
            # Логируем в зависимости от статуса
            if response.status_code >= 500:
                logger.error(f"Server error: {log_data}")
            elif response.status_code >= 400:
                logger.warning(f"Client error: {log_data}")
            else:
                logger.info(f"Request processed: {log_data}")
        
        return response
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CRUDLoggingMiddleware(MiddlewareMixin):
    """Middleware для логирования CRUD операций через API"""
    
    CRUD_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Логируем только CRUD операции
        if request.method in self.CRUD_METHODS:
            request.crud_data = {
                'method': request.method,
                'path': request.path,
                'view': view_func.__name__ if view_func else 'unknown',
                'timestamp': timezone.now().isoformat(),
                'user': request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous',
                'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                'data': self._get_request_data(request),
            }
    
    def process_response(self, request, response):
        # Логируем результат CRUD операции
        if hasattr(request, 'crud_data') and request.method in self.CRUD_METHODS:
            crud_data = request.crud_data
            crud_data.update({
                'status_code': response.status_code,
                'response_time': timezone.now().isoformat(),
            })
            
            crud_logger.info(
                f"CRUD operation: {request.method} {request.path} - Status: {response.status_code}",
                extra=crud_data
            )
        
        return response
    
    def _get_request_data(self, request):
        """Безопасное извлечение данных запроса"""
        try:
            if request.method in ['POST', 'PUT', 'PATCH']:
                # Для JSON данных
                if request.content_type == 'application/json':
                    return json.loads(request.body.decode('utf-8'))
                # Для form data
                else:
                    return dict(request.POST)
        except:
            return {}
        
        return {}


class TokenAuthenticationMiddleware(MiddlewareMixin):
    """Middleware для аутентификации по токену"""
    
    def process_request(self, request):
        # Пропускаем статические файлы и админку
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return
        
        # Пробуем получить токен из заголовка
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Убираем 'Bearer '
            
            from .authentication import TokenService
            user = TokenService.get_user_from_token(token)
            
            if user:
                request.user = user
                request.auth = token
                
                # Логируем успешную аутентификацию по токену
                security_logger.info(
                    f"User authenticated via token: {user.username}",
                    extra={
                        'user_id': user.id,
                        'username': user.username,
                        'ip': self._get_client_ip(request),
                        'path': request.path,
                    }
                )


class UserActivityMiddleware(MiddlewareMixin):
    """Middleware для отслеживания активности пользователей"""
    
    def process_response(self, request, response):
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Логируем активность пользователя
            security_logger.info(
                f"User activity: {request.user.username} accessed {request.path}",
                extra={
                    'user_id': request.user.id,
                    'username': request.user.username,
                    'path': request.path,
                    'method': request.method,
                    'status_code': response.status_code,
                    'timestamp': timezone.now().isoformat(),
                }
            )
        
        return response
