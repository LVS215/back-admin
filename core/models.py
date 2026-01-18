import secrets
import hashlib
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger('crud')

class TimestampMixin(models.Model):
    """Миксин для добавления временных меток"""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class AuditMixin(models.Model):
    """Миксин для аудита изменений"""
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_%(class)s_set'
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='updated_%(class)s_set'
    )
    
    class Meta:
        abstract = True

class Category(TimestampMixin):
    """Категории статей"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Логирование создания/обновления категории
        if is_new:
            logger.info(
                f"Category created: {self.name} (ID: {self.id})",
                extra={
                    'model': 'Category',
                    'action': 'create',
                    'object_id': self.id,
                    'object_name': self.name,
                }
            )
        else:
            logger.info(
                f"Category updated: {self.name} (ID: {self.id})",
                extra={
                    'model': 'Category',
                    'action': 'update',
                    'object_id': self.id,
                    'object_name': self.name,
                }
            )

class UserProfile(TimestampMixin):
    """Расширенный профиль пользователя"""
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    website = models.URLField(blank=True)
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"Profile of {self.user.username}"

class AuthToken(TimestampMixin):
    """
    Токен аутентификации (256 символов)
    Требование: Пользователь регистрируется через username и password, 
    сервер генерирует токен (256 случайных символов)
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='auth_tokens'
    )
    token = models.CharField(max_length=256, unique=True, db_index=True)  # 256 символов точно!
    token_hash = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=100, default='Default token')
    last_used = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Auth Token"
        verbose_name_plural = "Auth Tokens"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['token_hash']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Token for {self.user.username}"
    
    def save(self, *args, **kwargs):
        # Генерируем токен при создании
        if not self.token:
            self.token = self.generate_token()
        
        # Хэшируем токен для безопасного хранения
        if self.token and not self.token_hash:
            self.token_hash = hashlib.sha256(self.token.encode()).hexdigest()
        
        # Устанавливаем срок действия (30 дней по умолчанию)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=30)
        
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_token(cls):
        """
        Генерация токена 256 символов
        Используем secrets для криптографически безопасной генерации
        """
        # 192 байта в base64 дадут 256 символов
        return secrets.token_urlsafe(192)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        return self.is_active and not self.is_expired

class Post(TimestampMixin, AuditMixin):
    """Статьи блога"""
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_ARCHIVED, 'Archived'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    content = models.TextField()
    excerpt = models.TextField(max_length=500, blank=True)
    
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='posts'
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='posts'
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default=STATUS_DRAFT,
        db_index=True
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['author']),
            models.Index(fields=['category']),
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Устанавливаем published_at при публикации
        if self.status == self.STATUS_PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)
        
        # Логирование создания/обновления статьи
        if is_new:
            logger.info(
                f"Post created: {self.title} (ID: {self.id}) by {self.author.username}",
                extra={
                    'model': 'Post',
                    'action': 'create',
                    'object_id': self.id,
                    'object_name': self.title,
                    'author': self.author.username,
                    'author_id': self.author.id,
                }
            )
        else:
            logger.info(
                f"Post updated: {self.title} (ID: {self.id}) by {self.author.username}",
                extra={
                    'model': 'Post',
                    'action': 'update',
                    'object_id': self.id,
                    'object_name': self.title,
                    'author': self.author.username,
                    'author_id': self.author.id,
                }
            )
    
    def delete(self, *args, **kwargs):
        # Логирование удаления статьи
        logger.warning(
            f"Post deleted: {self.title} (ID: {self.id}) by {self.author.username}",
            extra={
                'model': 'Post',
                'action': 'delete',
                'object_id': self.id,
                'object_name': self.title,
                'author': self.author.username,
                'author_id': self.author.id,
            }
        )
        super().delete(*args, **kwargs)

class Comment(TimestampMixin, AuditMixin):
    """Комментарии к статьям"""
    post = models.ForeignKey(
        Post, 
        on_delete=models.CASCADE, 
        related_name='comments'
    )
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='comments'
    )
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='replies'
    )
    
    content = models.TextField()
    is_approved = models.BooleanField(default=True, db_index=True)
    
    class Meta:
        verbose_name = "Comment"
        verbose_name_plural = "Comments"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'created_at']),
            models.Index(fields=['author']),
            models.Index(fields=['is_approved']),
        ]
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Логирование создания/обновления комментария
        if is_new:
            logger.info(
                f"Comment created: (ID: {self.id}) by {self.author.username} on post {self.post.id}",
                extra={
                    'model': 'Comment',
                    'action': 'create',
                    'object_id': self.id,
                    'post_id': self.post.id,
                    'author': self.author.username,
                    'author_id': self.author.id,
                }
            )
        else:
            logger.info(
                f"Comment updated: (ID: {self.id}) by {self.author.username}",
                extra={
                    'model': 'Comment',
                    'action': 'update',
                    'object_id': self.id,
                    'post_id': self.post.id,
                    'author': self.author.username,
                    'author_id': self.author.id,
                }
            )
    
    def delete(self, *args, **kwargs):
        # Логирование удаления комментария
        logger.warning(
            f"Comment deleted: (ID: {self.id}) by {self.author.username}",
            extra={
                'model': 'Comment',
                'action': 'delete',
                'object_id': self.id,
                'post_id': self.post.id,
                'author': self.author.username,
                'author_id': self.author.id,
            }
        )
        super().delete(*args, **kwargs)

# Сигналы для автоматического логирования
@receiver(post_save, sender=User)
def log_user_save(sender, instance, created, **kwargs):
    """Логирование создания/обновления пользователя"""
    logger = logging.getLogger('security')
    if created:
        logger.info(
            f"User created: {instance.username} (ID: {instance.id})",
            extra={
                'model': 'User',
                'action': 'create',
                'object_id': instance.id,
                'object_name': instance.username,
            }
        )
    else:
        logger.info(
            f"User updated: {instance.username} (ID: {instance.id})",
            extra={
                'model': 'User',
                'action': 'update',
                'object_id': instance.id,
                'object_name': instance.username,
            }
        )

@receiver(post_delete, sender=User)
def log_user_delete(sender, instance, **kwargs):
    """Логирование удаления пользователя"""
    logger = logging.getLogger('security')
    logger.warning(
        f"User deleted: {instance.username} (ID: {instance.id})",
        extra={
            'model': 'User',
            'action': 'delete',
            'object_id': instance.id,
            'object_name': instance.username,
        }
    )

@receiver(post_save, sender=AuthToken)
def log_token_save(sender, instance, created, **kwargs):
    """Логирование создания/обновления токена"""
    logger = logging.getLogger('security')
    if created:
        logger.info(
            f"Token created for user: {instance.user.username}",
            extra={
                'model': 'AuthToken',
                'action': 'create',
                'object_id': instance.id,
                'user_id': instance.user.id,
                'username': instance.user.username,
            }
        )
    else:
        # Логируем только важные изменения
        logger.info(
            f"Token updated for user: {instance.user.username}",
            extra={
                'model': 'AuthToken',
                'action': 'update',
                'object_id': instance.id,
                'user_id': instance.user.id,
                'username': instance.user.username,
            }
        )
