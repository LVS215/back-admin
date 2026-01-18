"""
Кастомная аутентификация с 256-символьными токенами
Требование: Авторизация через этот токен (в заголовке или body)
"""
import logging
from typing import Optional
from ninja.security import HttpBearer
from ninja.errors import AuthenticationError
from django.utils import timezone
from django.contrib.auth.models import User

from .models import AuthToken

logger = logging.getLogger('security')

class TokenAuthentication(HttpBearer):
    """
    Аутентификация через 256-символьный токен
    Поддерживает токен в заголовке Authorization: Bearer <token>
    """
    
    def authenticate(self, request, token: str) -> Optional[User]:
        # Проверка длины токена (должен быть 256 символов)
        if len(token) != 256:
            logger.warning(
                f"Invalid token length: {len(token)} characters",
                extra={
                    'token_length': len(token),
                    'expected_length': 256,
                    'ip': self._get_client_ip(request),
                }
            )
            raise AuthenticationError("Invalid token length")
        
        try:
            # Ищем активный, не просроченный токен
            auth_token = AuthToken.objects.select_related('user').get(
                token=token,
                is_active=True,
                expires_at__gt=timezone.now()
            )
            
            # Обновляем время последнего использования
            auth_token.last_used = timezone.now()
            auth_token.save(update_fields=['last_used'])
            
            # Логируем успешную аутентификацию
            logger.info(
                f"User authenticated: {auth_token.user.username}",
                extra={
                    'user_id': auth_token.user.id,
                    'username': auth_token.user.username,
                    'token_id': auth_token.id,
                    'ip': self._get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                }
            )
            
            return auth_token.user
            
        except AuthToken.DoesNotExist:
            # Логируем неудачную попытку аутентификации
            logger.warning(
                "Invalid token provided",
                extra={
                    'token_prefix': token[:20] if token else 'empty',
                    'ip': self._get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                }
            )
            raise AuthenticationError("Invalid or expired token")
        except Exception as e:
            logger.error(
                f"Authentication error: {str(e)}",
                extra={
                    'error': str(e),
                    'ip': self._get_client_ip(request),
                }
            )
            raise AuthenticationError("Authentication failed")
    
    def _get_client_ip(self, request):
        """Получение IP адреса клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class TokenService:
    """Сервис для работы с токенами"""
    
    @staticmethod
    def create_user_token(user: User, token_name: str = "Default") -> str:
        """
        Создание нового токена для пользователя
        Возвращает сам токен (256 символов)
        """
        # Генерируем новый токен
        token = AuthToken.generate_token()
        
        # Создаем запись в базе
        auth_token = AuthToken.objects.create(
            user=user,
            token=token,
            name=token_name,
            expires_at=timezone.now() + timezone.timedelta(days=30)
        )
        
        logger.info(
            f"Token created for user: {user.username}",
            extra={
                'user_id': user.id,
                'username': user.username,
                'token_id': auth_token.id,
                'token_name': token_name,
            }
        )
        
        return token
    
    @staticmethod
    def revoke_user_tokens(user: User, reason: str = "manual_revocation"):
        """Отзыв всех токенов пользователя"""
        tokens = AuthToken.objects.filter(user=user, is_active=True)
        count = tokens.count()
        
        tokens.update(is_active=False)
        
        logger.info(
            f"All tokens revoked for user: {user.username}",
            extra={
                'user_id': user.id,
                'username': user.username,
                'token_count': count,
                'reason': reason,
            }
        )
    
    @staticmethod
    def validate_token_strength(token: str) -> bool:
        """
        Валидация сложности токена
        Проверяет, что токен содержит достаточную энтропию
        """
        if len(token) != 256:
            return False
        
        # Простая проверка разнообразия символов
        unique_chars = len(set(token))
        # Для 256 символов base64 должно быть много уникальных
        return unique_chars > 50  # Минимум 50 уникальных символов
    
    @staticmethod
    def get_user_from_token(token: str) -> Optional[User]:
        """Получение пользователя по токену"""
        try:
            auth_token = AuthToken.objects.select_related('user').get(
                token=token,
                is_active=True,
                expires_at__gt=timezone.now()
            )
            return auth_token.user
        except AuthToken.DoesNotExist:
            return None
