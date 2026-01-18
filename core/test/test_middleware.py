# core/tests/test_middleware.py
from django.test import TestCase
from django.test.client import RequestFactory
from django.http import HttpResponse

class MiddlewareTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
    
    def test_middleware_integration(self):
        """Тест интеграции middleware"""
        from core.middleware import LoggingMiddleware
        
        def dummy_view(request):
            return HttpResponse("OK")
        
        middleware = LoggingMiddleware(dummy_view)
        request = self.factory.get('/test-path/')
        
        # Проверяем, что middleware не вызывает ошибок
        try:
            response = middleware(request)
            self.assertEqual(response.status_code, 200)
        except Exception as e:
            self.fail(f"Middleware failed with error: {e}")