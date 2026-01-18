from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
import time
import logging

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.start_time = time.time()
        
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            logger.info(
                f"{request.method} {request.path} "
                f"{response.status_code} {duration:.2f}s"
            )
        return response

class RateLimitMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/api/'):
            ip = request.META.get('REMOTE_ADDR')
            key = f'ratelimit:{ip}'
            count = cache.get(key, 0)
            
            if count > 100:  # 100 запросов в минуту
                logger.warning(f'Rate limit exceeded for IP: {ip}')
                from django.http import JsonResponse
                return JsonResponse(
                    {'error': 'Rate limit exceeded'},
                    status=429
                )
            
            cache.set(key, count + 1, timeout=60)
        
        return None
