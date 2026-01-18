from ninja import Router
from ninja.errors import AuthenticationError
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from ninja_jwt.tokens import RefreshToken
import logging

from core.models import AuthToken, Profile
from .schemas import (
    UserRegisterSchema, 
    UserLoginSchema, 
    UserOutSchema,
    TokenResponseSchema
)

router = Router(tags=["Authentication"])
logger = logging.getLogger(__name__)

@router.post("/register", response=TokenResponseSchema)
def register(request, data: UserRegisterSchema):
    """Регистрация пользователя с генерацией 256-символьного токена"""
    if User.objects.filter(username=data.username).exists():
        logger.warning(f"Registration failed - username exists: {data.username}")
        raise AuthenticationError("Username already exists")
    
    if User.objects.filter(email=data.email).exists():
        logger.warning(f"Registration failed - email exists: {data.email}")
        raise AuthenticationError("Email already exists")
    
    # Создаем пользователя
    user = User.objects.create_user(
        username=data.username,
        email=data.email,
        password=data.password
    )
    
    # Создаем профиль
    Profile.objects.create(user=user)
    
    # Генерируем 256-символьный токен
    token = AuthToken.generate_token()
    
    # Сохраняем токен в базе
    auth_token = AuthToken.objects.create(
        user=user,
        token=token,
        expires_at=timezone.now() + timezone.timedelta(days=30)
    )
    
    # Логирование
    logger.info(f"User registered: {user.username}")
    logger.info(f"Token generated for user: {user.username}")
    
    return {
        "message": "User registered successfully",
        "token": token,
        "user": UserOutSchema.from_orm(user)
    }

@router.post("/login", response=TokenResponseSchema)
def login_user(request, data: UserLoginSchema):
    """Аутентификация пользователя"""
    user = authenticate(username=data.username, password=data.password)
    
    if not user:
        logger.warning(f"Login failed for username: {data.username}")
        raise AuthenticationError("Invalid credentials")
    
    # Генерируем новый 256-символьный токен
    token = AuthToken.generate_token()
    
    # Сохраняем токен
    auth_token = AuthToken.objects.create(
        user=user,
        token=token,
        ip_address=request.META.get('REMOTE_ADDR'),
        device_info=request.META.get('HTTP_USER_AGENT', ''),
        expires_at=timezone.now() + timezone.timedelta(days=30)
    )
    
    # Логирование
    logger.info(f"User logged in: {user.username}")
    logger.info(f"Token issued for user: {user.username}")
    
    return {
        "message": "Login successful",
        "token": token,
        "user": UserOutSchema.from_orm(user)
    }

@router.post("/logout")
def logout_user(request):
    """Выход пользователя"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if token:
        try:
            auth_token = AuthToken.objects.get(token=token, is_active=True)
            auth_token.is_active = False
            auth_token.save()
            logger.info(f"User logged out: {auth_token.user.username}")
        except AuthToken.DoesNotExist:
            pass
    
    return {"message": "Logged out successfully"}

@router.get("/me", response=UserOutSchema, auth=JWTAuth())
def get_current_user(request):
    """Получение информации о текущем пользователе"""
    logger.info(f"User profile accessed: {request.user.username}")
    return request.user
