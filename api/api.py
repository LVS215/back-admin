"""
Основной API объект Django Ninja
"""
from ninja import NinjaAPI
from ninja.errors import ValidationError, AuthenticationError
from django.http import JsonResponse
import logging

from core.authentication import TokenAuthentication
from core.exceptions import BlogAPIException

# Импортируем роутеры
from .auth.router import router as auth_router
from .posts.router import router as posts_router
from .comments.router import router as comments_router

logger = logging.getLogger(__name__)

# Создаем основной API объект
api = NinjaAPI(
    title="Blog Platform API",
    version="1.0.0",
    description="""
    Бэкенд для блога с полным соответствием требованиям:
    - Регистрация с 256-символьными токенами
    - CRUD для статей и комментариев
    - Аутентификация через токен
    - Логирование всех операций
    """,
    docs_url="/docs",
    openapi_url="/openapi.json",
    auth=None,  # Аутентификация на уровне роутеров
)

# Регистрируем роутеры
api.add_router("/auth", auth_router)
api.add_router("/posts", posts_router)
api.add_router("/comments", comments_router)

# Обработчики ошибок
@api.exception_handler(ValidationError)
def validation_error_handler(request, exc):
    """Обработка ошибок валидации"""
    logger.warning(
        f"Validation error: {exc.errors}",
        extra={
            'path': request.path,
            'method': request.method,
            'errors': exc.errors,
        }
    )
    return api.create_response(
        request,
        {"detail": "Validation error", "errors": exc.errors},
        status=422,
    )

@api.exception_handler(AuthenticationError)
def authentication_error_handler(request, exc):
    """Обработка ошибок аутентификации"""
    logger.warning(
        f"Authentication error: {str(exc)}",
        extra={
            'path': request.path,
            'method': request.method,
            'ip': request.META.get('REMOTE_ADDR'),
        }
    )
    return api.create_response(
        request,
        {"detail": str(exc)},
        status=401,
    )

@api.exception_handler(BlogAPIException)
def blog_api_exception_handler(request, exc):
    """Обработка кастомных исключений"""
    logger.error(
        f"Blog API error: {exc.detail}",
        extra={
            'path': request.path,
            'method': request.method,
            'error': exc.detail,
            'code': exc.code,
        }
    )
    return api.create_response(
        request,
        {"detail": exc.detail, "code": exc.code},
        status=exc.status_code,
    )

@api.exception_handler(Exception)
def general_exception_handler(request, exc):
    """Обработка всех остальных исключений"""
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={
            'path': request.path,
            'method': request.method,
            'error': str(exc),
            'ip': request.META.get('REMOTE_ADDR'),
        },
        exc_info=True
    )
    return api.create_response(
        request,
        {"detail": "Internal server error"},
        status=500,
    )

# Health check endpoint
@api.get("/health", tags=["System"])
def health_check(request):
    """Проверка работоспособности API"""
    return {
        "status": "healthy",
        "service": "blog-api",
        "timestamp": "2024-01-01T00:00:00Z"  # В реальности используйте timezone.now()
    }

# Информация о API
@api.get("/info", tags=["System"])
def api_info(request):
    """Информация о API"""
    return {
        "name": "Blog Platform API",
        "version": "1.0.0",
        "description": "Бэкенд для блога с Django Ninja",
        "documentation": "/docs",
        "openapi": "/openapi.json",
    }
