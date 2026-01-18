"""
Права доступа для проверки владельца объектов
Требование: Пользователь может редактировать/удалять только свои статьи/комментарии
"""
from typing import Any
from ninja.security import APIKeyQuery
from django.contrib.auth.models import AnonymousUser

from .models import Post, Comment

class IsAuthenticated:
    """Проверка аутентификации пользователя"""
    
    def __call__(self, request) -> bool:
        return bool(request.auth and request.user)


class IsOwnerOrReadOnly:
    """
    Разрешает доступ только владельцу объекта
    Для GET запросов доступ открыт всем
    """
    
    def __init__(self, model_class, owner_field='author'):
        self.model_class = model_class
        self.owner_field = owner_field
    
    def __call__(self, request) -> bool:
        # Разрешаем все GET, HEAD, OPTIONS запросы
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # Для остальных методов проверяем владельца
        obj_id = self._get_object_id_from_request(request)
        if not obj_id:
            return False
        
        try:
            obj = self.model_class.objects.get(pk=obj_id)
            owner = getattr(obj, self.owner_field)
            
            # Проверяем, что пользователь - владелец
            return owner == request.user
        except self.model_class.DoesNotExist:
            return False
    
    def _get_object_id_from_request(self, request) -> Any:
        """Извлечение ID объекта из запроса"""
        # Из URL path parameters
        if hasattr(request, 'path_params'):
            for key, value in request.path_params.items():
                if key.endswith('_id') or key == 'id':
                    return value
        
        # Из query parameters
        for key, value in request.GET.items():
            if key.endswith('_id') or key == 'id':
                return value
        
        return None


class IsPostOwner(IsOwnerOrReadOnly):
    """Проверка владельца статьи"""
    def __init__(self):
        super().__init__(Post, 'author')


class IsCommentOwner(IsOwnerOrReadOnly):
    """Проверка владельца комментария"""
    def __init__(self):
        super().__init__(Comment, 'author')


class IsAdminUser:
    """Проверка прав администратора"""
    
    def __call__(self, request) -> bool:
        return bool(request.user and request.user.is_staff)


class HasObjectPermission:
    """Проверка прав на конкретный объект"""
    
    def __init__(self, permission_checker):
        self.permission_checker = permission_checker
    
    def __call__(self, request) -> bool:
        return self.permission_checker(request.user, request)
