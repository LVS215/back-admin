# core/tests/test_logging.py
import structlog
from django.test import TestCase
from django.test.client import RequestFactory

class LoggingTestCase(TestCase):
    def test_structlog_configuration(self):
        """Тест конфигурации structlog"""
        logger = structlog.get_logger(__name__)
        
        # Проверяем, что логирование работает без ошибок
        try:
            logger.info("test_log_message", test_field="test_value")
        except Exception as e:
            self.fail(f"Logging failed with error: {e}")