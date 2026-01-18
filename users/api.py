from ninja import Router
from ninja.errors import HttpError
from django.contrib.auth import authenticate
from ninja_jwt.tokens import RefreshToken
import structlog

from users.models import User
from users.schemas import UserIn, UserOut, AuthIn, TokenOut

router = Router(tags=["users"])
logger = structlog.get_logger(__name__)

@router.post("/register", response=TokenOut, auth=None)
def register(request, payload: UserIn):
    """Регистрация нового пользователя"""
    if User.objects.filter(username=payload.username).exists():
        logger.warning("Registration failed: username already exists", username=payload.username)
        raise HttpError(400, "Username already exists")
    
    user = User.objects.create_user(
        username=payload.username,
        password=payload.password,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    
    refresh = RefreshToken.for_user(user)
    
    logger.info("User registered successfully", user_id=str(user.id), username=user.username)
    
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserOut.from_orm(user)
    }

@router.post("/login", response=TokenOut, auth=None)
def login(request, payload: AuthIn):
    """Аутентификация пользователя"""
    user = authenticate(username=payload.username, password=payload.password)
    
    if not user:
        logger.warning("Login failed: invalid credentials", username=payload.username)
        raise HttpError(401, "Invalid credentials")
    
    refresh = RefreshToken.for_user(user)
    
    logger.info("User logged in", user_id=str(user.id), username=user.username)
    
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserOut.from_orm(user)
    }

@router.get("/me", response=UserOut)
def get_current_user(request):
    """Получение информации о текущем пользователе"""
    return request.auth

@router.put("/me", response=UserOut)
def update_current_user(request, payload: UserIn):
    """Обновление информации о текущем пользователе"""
    user = request.auth
    
    if User.objects.filter(username=payload.username).exclude(id=user.id).exists():
        raise HttpError(400, "Username already taken")
    
    user.username = payload.username
    user.email = payload.email
    user.first_name = payload.first_name
    user.last_name = payload.last_name
    
    if payload.password:
        user.set_password(payload.password)
    
    user.save()
    
    logger.info("User updated", user_id=str(user.id))
    
    return user