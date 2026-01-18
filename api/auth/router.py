"""
Роутер для аутентификации и регистрации
Требование: Регистрация через username и password, генерация токена 256 символов
"""
from ninja import Router
from ninja.errors import AuthenticationError
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import IntegrityError
import logging

from core.authentication import TokenService
from core.exceptions import BlogAPIException
from .schemas import (
    UserRegisterIn, 
    UserRegisterOut,
    UserLoginIn,
    UserLoginOut,
    UserProfileOut,
    TokenRevokeIn,
)
from core.permissions import IsAuthenticated

router = Router(tags=["Authentication"])
logger = logging.getLogger(__name__)

@router.post("/register", response=UserRegisterOut)
def register(request, data: UserRegisterIn):
    """
    Регистрация нового пользователя
    Генерирует токен 256 символов
    """
    # Валидация пароля
    if len(data.password) < 8:
        raise BlogAPIException(
            detail="Password must be at least 8 characters long",
            code="password_too_short",
            status_code=400,
        )
    
    if data.password != data.password_confirm:
        raise BlogAPIException(
            detail="Passwords do not match",
            code="passwords_mismatch",
            status_code=400,
        )
    
    try:
        # Создаем пользователя
        user = User.objects.create_user(
            username=data.username,
            email=data.email,
            password=data.password
        )
        
        logger.info(
            f"User registered successfully: {user.username}",
            extra={
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'ip': request.META.get('REMOTE_ADDR'),
            }
        )
        
        # Создаем профиль
        from core.models import UserProfile
        UserProfile.objects.create(user=user)
        
        # Генерируем токен 256 символов
        token = TokenService.create_user_token(user, "Registration token")
        
        return {
            "message": "User registered successfully",
            "token": token,
            "token_length": len(token),  # Должно быть 256
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            }
        }
        
    except IntegrityError as e:
        # Проверяем, какое поле вызвало ошибку
        if "username" in str(e).lower():
            raise BlogAPIException(
                detail="Username already exists",
                code="username_exists",
                status_code=400,
            )
        elif "email" in str(e).lower():
            raise BlogAPIException(
                detail="Email already exists",
                code="email_exists",
                status_code=400,
            )
        else:
            raise BlogAPIException(
                detail="Registration failed",
                code="registration_failed",
                status_code=400,
            )
    
    except Exception as e:
        logger.error(
            f"Registration error: {str(e)}",
            extra={
                'username': data.username,
                'email': data.email,
                'ip': request.META.get('REMOTE_ADDR'),
            },
            exc_info=True
        )
        raise BlogAPIException(
            detail="Registration failed",
            code="registration_error",
            status_code=500,
        )


@router.post("/login", response=UserLoginOut)
def login(request, data: UserLoginIn):
    """
    Аутентификация пользователя
    Возвращает новый токен 256 символов
    """
    user = authenticate(username=data.username, password=data.password)
    
    if not user:
        logger.warning(
            "Login failed: invalid credentials",
            extra={
                'username': data.username,
                'ip': request.META.get('REMOTE_ADDR'),
            }
        )
        raise AuthenticationError("Invalid username or password")
    
    # Проверяем, активен ли пользователь
    if not user.is_active:
        logger.warning(
            "Login failed: user inactive",
            extra={
                'user_id': user.id,
                'username': user.username,
                'ip': request.META.get('REMOTE_ADDR'),
            }
        )
        raise AuthenticationError("User account is inactive")
    
    # Генерируем новый токен
    token = TokenService.create_user_token(user, "Login token")
    
    logger.info(
        f"User logged in successfully: {user.username}",
        extra={
            'user_id': user.id,
            'username': user.username,
            'ip': request.META.get('REMOTE_ADDR'),
        }
    )
    
    return {
        "message": "Login successful",
        "token": token,
        "token_length": len(token),  # Должно быть 256
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
    }


@router.post("/logout", auth=IsAuthenticated())
def logout(request):
    """
    Выход пользователя (отзыв текущего токена)
    """
    token = request.auth
    if token:
        from core.models import AuthToken
        try:
            auth_token = AuthToken.objects.get(token=token, is_active=True)
            auth_token.is_active = False
            auth_token.save()
            
            logger.info(
                f"User logged out: {request.user.username}",
                extra={
                    'user_id': request.user.id,
                    'username': request.user.username,
                    'token_id': auth_token.id,
                    'ip': request.META.get('REMOTE_ADDR'),
                }
            )
        except AuthToken.DoesNotExist:
            pass
    
    return {"message": "Logged out successfully"}


@router.post("/revoke-all", auth=IsAuthenticated())
def revoke_all_tokens(request, data: TokenRevokeIn):
    """
    Отзыв всех токенов пользователя
    """
    TokenService.revoke_user_tokens(request.user, data.reason)
    
    logger.info(
        f"All tokens revoked for user: {request.user.username}",
        extra={
            'user_id': request.user.id,
            'username': request.user.username,
            'reason': data.reason,
            'ip': request.META.get('REMOTE_ADDR'),
        }
    )
    
    return {"message": "All tokens have been revoked"}


@router.get("/profile", response=UserProfileOut, auth=IsAuthenticated())
def get_profile(request):
    """
    Получение профиля текущего пользователя
    """
    user = request.user
    
    logger.info(
        f"Profile accessed: {user.username}",
        extra={
            'user_id': user.id,
            'username': user.username,
            'ip': request.META.get('REMOTE_ADDR'),
        }
    )
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "date_joined": user.date_joined,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
    }


@router.get("/tokens", auth=IsAuthenticated())
def list_tokens(request):
    """
    Список активных токенов пользователя
    """
    from core.models import AuthToken
    from django.utils import timezone
    
    tokens = AuthToken.objects.filter(
        user=request.user,
        is_active=True,
        expires_at__gt=timezone.now()
    ).values('id', 'name', 'created_at', 'last_used', 'expires_at')
    
    logger.info(
        f"Tokens listed for user: {request.user.username}",
        extra={
            'user_id': request.user.id,
            'username': request.user.username,
            'token_count': tokens.count(),
            'ip': request.META.get('REMOTE_ADDR'),
        }
    )
    
    return {"tokens": list(tokens)}
