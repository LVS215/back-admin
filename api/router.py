from ninja import NinjaAPI
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.authentication import JWTAuth

from .auth import router as auth_router
from .posts import router as posts_router
from .comments import router as comments_router

api = NinjaAPI(
    title="Blog API",
    version="1.0.0",
    description="API for blogging platform with Django Ninja",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Подключаем JWT аутентификацию
api.register_controllers(NinjaJWTDefaultController)

# Подключаем роутеры
api.add_router("/auth", auth_router)
api.add_router("/posts", posts_router)
api.add_router("/comments", comments_router)

@api.get("/health")
def health_check(request):
    """Health check endpoint"""
    return {"status": "healthy", "service": "blog-api"}
