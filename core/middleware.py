import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware для логирования всех запросов"""
    
    def process_request(self, request):
        request.start_time = time.time()
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            # Логируем информацию о запросе
            user = request.user.username if request.user.is_authenticated else 'anonymous'
            ip = request.META.get('REMOTE_ADDR', 'unknown')
            
            log_message = (
                f"method={request.method} "
                f"path={request.path} "
                f"status={response.status_code} "
                f"duration={duration:.3f}s "
                f"user={user} "
                f"ip={ip}"
            )
            
            if response.status_code >= 400:
                logger.warning(log_message)
            else:
                logger.info(log_message)
        
        return response

class SecurityHeadersMiddleware(MiddlewareMixin):
    """Middleware для security headers"""
    
    def process_response(self, request, response):
        # Базовые security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        # CORS headers (для API)
        if request.path.startswith('/api/'):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        
        return response
