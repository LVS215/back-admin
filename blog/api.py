from ninja import NinjaAPI
from ninja.security import HttpBearer
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.authentication import JWTAuth
from django.http import HttpRequest
import structlog

from users.api import router as users_router
from articles.api import router as articles_router
from comments.api import router as comments_router

logger = structlog.get_logger(__name__)

api = NinjaAPI(
    title="Blog API",
    version="1.0.0",
    description="API для блога с аутентификацией и CRUD операциями",
    auth=JWTAuth(),
)

# Регистрация JWT контроллера
api.add_router("/auth", NinjaJWTDefaultController())

# Регистрация маршрутов
api.add_router("/users", users_router)
api.add_router("/articles", articles_router)
api.add_router("/comments", comments_router)

@api.get("/health", auth=None)
def health_check(request: HttpRequest):
    """Проверка здоровья API"""
    logger.info("Health check requested")
    return {"status": "healthy", "service": "blog-api"}