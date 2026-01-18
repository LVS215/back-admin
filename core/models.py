from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinLengthValidator, EmailValidator, RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db.models import Q, F, Count, Avg, Max, Min, Sum
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings
from django.core.cache import cache

import uuid
import secrets
import hashlib
from typing import Optional, List, Dict, Any
from datetime import timedelta
from enum import Enum


class CustomUserManager(BaseUserManager):
    """
    Кастомный менеджер пользователей с поддержкой email как username
    """
    
    def create_user(self, email: str, username: str = None, password: str = None, **extra_fields):
        """
        Создает и сохраняет обычного пользователя
        """
        if not email:
            raise ValueError(_('The Email field must be set'))
        
        email = self.normalize_email(email)
        
        if not username:
            # Генерируем username из email
            username = email.split('@')[0]
            # Убедимся, что username уникален
            counter = 1
            original_username = username
            while self.model.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1
        
        user = self.model(email=email, username=username, **extra_fields)
        
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email: str, username: str = None, password: str = None, **extra_fields):
        """
        Создает и сохраняет суперпользователя
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('email_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractUser):
    """
    Расширенная модель пользователя
    """
    
    class UserRole(models.TextChoices):
        ADMIN = 'admin', _('Administrator')
        EDITOR = 'editor', _('Editor')
        AUTHOR = 'author', _('Author')
        USER = 'user', _('User')
        GUEST = 'guest', _('Guest')
    
    # Переопределяем username и email
    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[AbstractUser.username_validator],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )
    email = models.EmailField(
        _('email address'),
        unique=True,
        validators=[EmailValidator()],
        error_messages={
            'unique': _("A user with that email already exists."),
        }
    )
    
    # Дополнительные поля
    bio = models.TextField(
        _('biography'),
        max_length=2000,
        blank=True,
        null=True,
        help_text=_('Tell us about yourself')
    )
    avatar = models.ImageField(
        _('avatar'),
        upload_to='avatars/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text=_('Profile picture')
    )
    birth_date = models.DateField(
        _('birth date'),
        blank=True,
        null=True,
        help_text=_('Date of birth')
    )
    website = models.URLField(
        _('website'),
        max_length=200,
        blank=True,
        null=True
    )
    location = models.CharField(
        _('location'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Токен для API (альтернатива JWT)
    api_token = models.CharField(
        _('API token'),
        max_length=255,
        unique=True,
        editable=False,
        blank=True,
        null=True,
        db_index=True
    )
    api_token_created = models.DateTimeField(
        _('API token created'),
        blank=True,
        null=True
    )
    api_token_expires = models.DateTimeField(
        _('API token expires'),
        blank=True,
        null=True
    )
    
    # Верификация
    email_verified = models.BooleanField(
        _('email verified'),
        default=False
    )
    is_verified = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_('Designates whether the user has been verified by staff.')
    )
    verification_token = models.CharField(
        _('verification token'),
        max_length=64,
        blank=True,
        null=True,
        editable=False
    )
    verification_sent_at = models.DateTimeField(
        _('verification sent at'),
        blank=True,
        null=True
    )
    
    # Роли и разрешения
    role = models.CharField(
        _('role'),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.USER
    )
    
    # Статистика
    last_login_ip = models.GenericIPAddressField(
        _('last login IP'),
        blank=True,
        null=True
    )
    last_activity = models.DateTimeField(
        _('last activity'),
        auto_now=True
    )
    login_count = models.PositiveIntegerField(
        _('login count'),
        default=0
    )
    
    # Настройки
    receive_newsletter = models.BooleanField(
        _('receive newsletter'),
        default=True
    )
    email_notifications = models.BooleanField(
        _('email notifications'),
        default=True
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )
    
    objects = CustomUserManager()
    
    # Используем email как поле для входа
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_activity']),
            models.Index(fields=['role']),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(birth_date__lte=timezone.now().date()),
                name='birth_date_not_in_future'
            ),
        ]
    
    def __str__(self):
        return self.email
    
    def clean(self):
        """
        Валидация модели
        """
        super().clean()
        
        # Проверяем, что email уникален (кроме текущего пользователя)
        if self.email:
            qs = User.objects.filter(email=self.email)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({'email': _('A user with this email already exists.')})
        
        # Проверяем дату рождения
        if self.birth_date and self.birth_date > timezone.now().date():
            raise ValidationError({'birth_date': _('Birth date cannot be in the future.')})
    
    def save(self, *args, **kwargs):
        """
        Переопределяем save для генерации API токена
        """
        self.clean()
        
        if not self.api_token:
            self.generate_api_token()
        
        # Генерируем verification token при создании
        if not self.pk and not self.verification_token:
            self.verification_token = secrets.token_hex(32)
            self.verification_sent_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def generate_api_token(self, expires_days: int = 30) -> str:
        """
        Генерирует новый API токен
        """
        self.api_token = secrets.token_urlsafe(64)
        self.api_token_created = timezone.now()
        self.api_token_expires = timezone.now() + timedelta(days=expires_days)
        self.save(update_fields=['api_token', 'api_token_created', 'api_token_expires'])
        return self.api_token
    
    def is_api_token_valid(self) -> bool:
        """
        Проверяет валидность API токена
        """
        if not self.api_token or not self.api_token_expires:
            return False
        return timezone.now() < self.api_token_expires
    
    def get_full_name(self) -> str:
        """
        Возвращает полное имя пользователя
        """
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name if full_name else self.username
    
    def get_short_name(self) -> str:
        """
        Возвращает короткое имя пользователя
        """
        return self.first_name or self.username
    
    def get_absolute_url(self) -> str:
        """
        Возвращает абсолютный URL профиля пользователя
        """
        return reverse('user-profile', kwargs={'pk': self.pk})
    
    def get_avatar_url(self) -> Optional[str]:
        """
        Возвращает URL аватара или граватар
        """
        if self.avatar:
            return self.avatar.url
        
        # Генерируем граватар
        email_hash = hashlib.md5(self.email.lower().encode()).hexdigest()
        return f'https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=200'
    
    def increment_login_count(self, ip_address: str = None):
        """
        Увеличивает счетчик логинов
        """
        self.login_count = F('login_count') + 1
        self.last_login = timezone.now()
        self.last_activity = timezone.now()
        
        if ip_address:
            self.last_login_ip = ip_address
        
        self.save(update_fields=[
            'login_count', 'last_login', 'last_activity', 'last_login_ip'
        ])
    
    @property
    def is_editor(self) -> bool:
        """
        Проверяет, является ли пользователь редактором
        """
        return self.role in [self.UserRole.EDITOR, self.UserRole.ADMIN]
    
    @property
    def is_author(self) -> bool:
        """
        Проверяет, является ли пользователь автором
        """
        return self.role in [self.UserRole.AUTHOR, self.UserRole.EDITOR, self.UserRole.ADMIN]
    
    @property
    def is_admin(self) -> bool:
        """
        Проверяет, является ли пользователь администратором
        """
        return self.role == self.UserRole.ADMIN or self.is_superuser


class UserProfile(models.Model):
    """
    Дополнительный профиль пользователя
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('user')
    )
    
    # Социальные сети
    twitter = models.CharField(
        _('Twitter'),
        max_length=100,
        blank=True,
        null=True
    )
    facebook = models.CharField(
        _('Facebook'),
        max_length=100,
        blank=True,
        null=True
    )
    linkedin = models.CharField(
        _('LinkedIn'),
        max_length=100,
        blank=True,
        null=True
    )
    github = models.CharField(
        _('GitHub'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Настройки
    public_profile = models.BooleanField(
        _('public profile'),
        default=True
    )
    show_email = models.BooleanField(
        _('show email'),
        default=False
    )
    timezone = models.CharField(
        _('timezone'),
        max_length=50,
        default='UTC'
    )
    language = models.CharField(
        _('language'),
        max_length=10,
        default='en'
    )
    
    # Статистика
    article_count = models.PositiveIntegerField(
        _('article count'),
        default=0
    )
    comment_count = models.PositiveIntegerField(
        _('comment count'),
        default=0
    )
    total_likes_received = models.PositiveIntegerField(
        _('total likes received'),
        default=0
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )
    
    class Meta:
        verbose_name = _('user profile')
        verbose_name_plural = _('user profiles')
    
    def __str__(self):
        return f"Profile of {self.user.email}"
    
    def update_statistics(self):
        """
        Обновляет статистику профиля
        """
        self.article_count = self.user.articles.filter(status='published').count()
        self.comment_count = self.user.comments.filter(is_approved=True).count()
        self.total_likes_received = Article.objects.filter(
            author=self.user,
            status='published'
        ).aggregate(total=Sum('like_count'))['total'] or 0
        
        self.save(update_fields=[
            'article_count', 'comment_count', 'total_likes_received', 'updated_at'
        ])


class Category(models.Model):
    """
    Модель категории статей
    """
    name = models.CharField(
        _('name'),
        max_length=100,
        unique=True,
        db_index=True
    )
    slug = models.SlugField(
        _('slug'),
        max_length=100,
        unique=True,
        allow_unicode=True
    )
    description = models.TextField(
        _('description'),
        max_length=500,
        blank=True,
        null=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        verbose_name=_('parent category'),
        blank=True,
        null=True
    )
    
    # Визуальные настройки
    color = models.CharField(
        _('color'),
        max_length=7,
        default='#6c757d',
        help_text=_('Hex color code, e.g. #6c757d')
    )
    icon = models.CharField(
        _('icon'),
        max_length=50,
        blank=True,
        null=True,
        help_text=_('FontAwesome icon class, e.g. fas fa-code')
    )
    
    # Метаданные
    is_active = models.BooleanField(
        _('is active'),
        default=True
    )
    show_in_menu = models.BooleanField(
        _('show in menu'),
        default=True
    )
    sort_order = models.PositiveIntegerField(
        _('sort order'),
        default=0
    )
    
    # SEO
    meta_title = models.CharField(
        _('meta title'),
        max_length=200,
        blank=True,
        null=True
    )
    meta_description = models.TextField(
        _('meta description'),
        max_length=500,
        blank=True,
        null=True
    )
    
    # Статистика
    article_count = models.PositiveIntegerField(
        _('article count'),
        default=0,
        editable=False
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='created_categories',
        verbose_name=_('created by'),
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
            models.Index(fields=['parent']),
        ]
        constraints = [
            models.CheckConstraint(
                check=~Q(parent=F('id')),
                name='category_not_parent_of_itself'
            ),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """
        Валидация модели
        """
        if self.parent and self.parent == self:
            raise ValidationError({'parent': _('Category cannot be parent of itself.')})
        
        # Проверяем циклические зависимости
        if self.parent:
            current = self.parent
            while current:
                if current == self:
                    raise ValidationError({'parent': _('Circular dependency detected.')})
                current = current.parent
    
    def save(self, *args, **kwargs):
        """
        Переопределяем save для генерации slug
        """
        self.clean()
        
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        
        # Генерируем meta_title если не задан
        if not self.meta_title:
            self.meta_title = self.name
        
        super().save(*args, **kwargs)
        
        # Обновляем счетчик статей
        self.update_article_count()
    
    def update_article_count(self):
        """
        Обновляет счетчик статей в категории
        """
        count = self.articles.filter(status='published').count()
        Category.objects.filter(pk=self.pk).update(article_count=count)
    
    def get_absolute_url(self) -> str:
        """
        Возвращает абсолютный URL категории
        """
        return reverse('category-detail', kwargs={'slug': self.slug})
    
    def get_full_path(self) -> str:
        """
        Возвращает полный путь категории (включая родителей)
        """
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name
    
    @property
    def is_root(self) -> bool:
        """
        Проверяет, является ли категория корневой
        """
        return self.parent is None
    
    @property
    def depth(self) -> int:
        """
        Возвращает глубину категории в иерархии
        """
        depth = 0
        parent = self.parent
        while parent:
            depth += 1
            parent = parent.parent
        return depth
    
    def get_descendants(self, include_self: bool = False) -> models.QuerySet:
        """
        Возвращает всех потомков категории
        """
        from django.db.models import Q
        
        def get_children_ids(category_id):
            children_ids = []
            children = Category.objects.filter(parent_id=category_id)
            for child in children:
                children_ids.append(child.id)
                children_ids.extend(get_children_ids(child.id))
            return children_ids
        
        descendant_ids = get_children_ids(self.id)
        if include_self:
            descendant_ids.append(self.id)
        
        return Category.objects.filter(id__in=descendant_ids)
    
    def get_ancestors(self, include_self: bool = False) -> List['Category']:
        """
        Возвращает всех предков категории
        """
        ancestors = []
        parent = self.parent
        while parent:
            ancestors.append(parent)
            parent = parent.parent
        
        if include_self:
            ancestors = [self] + ancestors
        
        return list(reversed(ancestors))


class Tag(models.Model):
    """
    Модель тега для статей
    """
    name = models.CharField(
        _('name'),
        max_length=50,
        unique=True,
        db_index=True
    )
    slug = models.SlugField(
        _('slug'),
        max_length=50,
        unique=True,
        allow_unicode=True
    )
    description = models.TextField(
        _('description'),
        max_length=500,
        blank=True,
        null=True
    )
    
    # Статистика
    usage_count = models.PositiveIntegerField(
        _('usage count'),
        default=0,
        editable=False
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='created_tags',
        verbose_name=_('created by'),
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = _('tag')
        verbose_name_plural = _('tags')
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """
        Переопределяем save для генерации slug
        """
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        
        super().save(*args, **kwargs)
    
    def update_usage_count(self):
        """
        Обновляет счетчик использования тега
        """
        count = self.articles.filter(status='published').count()
        Tag.objects.filter(pk=self.pk).update(usage_count=count)
    
    def get_absolute_url(self) -> str:
        """
        Возвращает абсолютный URL тега
        """
        return reverse('tag-detail', kwargs={'slug': self.slug})


class Article(models.Model):
    """
    Модель статьи/поста блога
    """
    
    class ArticleStatus(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        PUBLISHED = 'published', _('Published')
        ARCHIVED = 'archived', _('Archived')
        PENDING = 'pending', _('Pending Review')
        REJECTED = 'rejected', _('Rejected')
    
    class ArticleType(models.TextChoices):
        ARTICLE = 'article', _('Article')
        TUTORIAL = 'tutorial', _('Tutorial')
        NEWS = 'news', _('News')
        REVIEW = 'review', _('Review')
        OTHER = 'other', _('Other')
    
    # Основные поля
    title = models.CharField(
        _('title'),
        max_length=200,
        db_index=True,
        validators=[
            MinLengthValidator(5, message=_('Title must be at least 5 characters long.'))
        ]
    )
    slug = models.SlugField(
        _('slug'),
        max_length=200,
        unique=True,
        allow_unicode=True,
        db_index=True
    )
    content = models.TextField(
        _('content'),
        validators=[
            MinLengthValidator(100, message=_('Content must be at least 100 characters long.'))
        ]
    )
    excerpt = models.TextField(
        _('excerpt'),
        max_length=500,
        blank=True,
        null=True,
        help_text=_('Short summary of the article (optional)')
    )
    
    # Связи
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='articles',
        verbose_name=_('author'),
        db_index=True
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='articles',
        verbose_name=_('category'),
        blank=True,
        null=True,
        db_index=True
    )
    tags = models.ManyToManyField(
        Tag,
        related_name='articles',
        verbose_name=_('tags'),
        blank=True
    )
    
    # Статус и тип
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=ArticleStatus.choices,
        default=ArticleStatus.DRAFT,
        db_index=True
    )
    article_type = models.CharField(
        _('type'),
        max_length=20,
        choices=ArticleType.choices,
        default=ArticleType.ARTICLE,
        db_index=True
    )
    
    # Изображения
    featured_image = models.ImageField(
        _('featured image'),
        upload_to='articles/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text=_('Main image for the article')
    )
    image_caption = models.CharField(
        _('image caption'),
        max_length=200,
        blank=True,
        null=True
    )
    
    # SEO
    meta_title = models.CharField(
        _('meta title'),
        max_length=200,
        blank=True,
        null=True
    )
    meta_description = models.TextField(
        _('meta description'),
        max_length=500,
        blank=True,
        null=True
    )
    canonical_url = models.URLField(
        _('canonical URL'),
        max_length=500,
        blank=True,
        null=True
    )
    
    # Флаги
    is_featured = models.BooleanField(
        _('is featured'),
        default=False,
        db_index=True,
        help_text=_('Featured articles appear in special sections')
    )
    is_pinned = models.BooleanField(
        _('is pinned'),
        default=False,
        db_index=True,
        help_text=_('Pinned articles appear at the top of lists')
    )
    allow_comments = models.BooleanField(
        _('allow comments'),
        default=True
    )
    allow_sharing = models.BooleanField(
        _('allow sharing'),
        default=True
    )
    require_login = models.BooleanField(
        _('require login'),
        default=False,
        help_text=_('Only logged-in users can view this article')
    )
    
    # Статистика
    view_count = models.PositiveIntegerField(
        _('view count'),
        default=0,
        editable=False
    )
    like_count = models.PositiveIntegerField(
        _('like count'),
        default=0,
        editable=False
    )
    comment_count = models.PositiveIntegerField(
        _('comment count'),
        default=0,
        editable=False
    )
    share_count = models.PositiveIntegerField(
        _('share count'),
        default=0,
        editable=False
    )
    
    # Время публикации
    published_at = models.DateTimeField(
        _('published at'),
        blank=True,
        null=True,
        db_index=True,
        help_text=_('Leave empty to save as draft')
    )
    scheduled_at = models.DateTimeField(
        _('scheduled at'),
        blank=True,
        null=True,
        db_index=True,
        help_text=_('Schedule publication for a future date')
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )
    last_edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='edited_articles',
        verbose_name=_('last edited by'),
        blank=True,
        null=True
    )
    last_edited_at = models.DateTimeField(
        _('last edited at'),
        blank=True,
        null=True
    )
    
    # Индексы для оптимизации
    class Meta:
        verbose_name = _('article')
        verbose_name_plural = _('articles')
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', 'published_at']),
            models.Index(fields=['author', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['is_featured', 'published_at']),
            models.Index(fields=['is_pinned', 'published_at']),
            models.Index(fields=['article_type', 'published_at']),
        ]
        permissions = [
            ('can_publish', 'Can publish articles'),
            ('can_feature', 'Can feature articles'),
            ('can_schedule', 'Can schedule articles'),
            ('can_moderate', 'Can moderate articles'),
        ]
    
    def __str__(self):
        return self.title
    
    def clean(self):
        """
        Валидация модели
        """
        super().clean()
        
        # Проверяем даты публикации
        if self.published_at and self.published_at > timezone.now():
            raise ValidationError({'published_at': _('Published date cannot be in the future.')})
        
        if self.scheduled_at and self.scheduled_at <= timezone.now():
            raise ValidationError({'scheduled_at': _('Scheduled date must be in the future.')})
        
        # Если статья опубликована, должна быть дата публикации
        if self.status == self.ArticleStatus.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        
        # Если есть scheduled_at, статус должен быть draft
        if self.scheduled_at and self.status != self.ArticleStatus.DRAFT:
            raise ValidationError({
                'status': _('Scheduled articles must be in draft status.')
            })
    
    def save(self, *args, **kwargs):
        """
        Переопределяем save для генерации slug и обработки публикации
        """
        self.clean()
        
        is_new = self.pk is None
        
        # Генерируем slug если новый или изменился title
        if is_new or 'title' in self.get_dirty_fields():
            base_slug = slugify(self.title, allow_unicode=True)
            slug = base_slug
            counter = 1
            
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        
        # Генерируем meta_title если не задан
        if not self.meta_title:
            self.meta_title = self.title
        
        # Генерируем excerpt если не задан
        if not self.excerpt and self.content:
            self.excerpt = self.content[:497] + '...' if len(self.content) > 500 else self.content
        
        # Обрабатываем публикацию
        if self.status == self.ArticleStatus.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        
        # Проверяем scheduled публикацию
        if self.scheduled_at and self.scheduled_at <= timezone.now():
            self.status = self.ArticleStatus.PUBLISHED
            self.published_at = self.scheduled_at
            self.scheduled_at = None
        
        super().save(*args, **kwargs)
        
        # Инвалидируем кэш
        self.invalidate_cache()
        
        # Создаем задачу для scheduled публикации если нужно
        if self.scheduled_at:
            from core.tasks import schedule_article_publication
            schedule_article_publication.apply_async(
                (self.pk,),
                eta=self.scheduled_at
            )
    
    def get_dirty_fields(self) -> Dict[str, Any]:
        """
        Возвращает изменившиеся поля
        """
        if not self.pk:
            return {}
        
        old = Article.objects.get(pk=self.pk)
        dirty = {}
        
        for field in self._meta.fields:
            if field.name in ['updated_at', 'last_edited_at']:
                continue
            
            old_value = getattr(old, field.name)
            new_value = getattr(self, field.name)
            
            if old_value != new_value:
                dirty[field.name] = new_value
        
        return dirty
    
    def invalidate_cache(self):
        """
        Инвалидирует кэш связанный со статьей
        """
        cache_keys = [
            f'article:{self.pk}',
            f'article_slug:{self.slug}',
            'articles:featured',
            'articles:recent',
            'articles:popular',
        ]
        
        if self.category:
            cache_keys.append(f'category_articles:{self.category.pk}')
        
        for tag in self.tags.all():
            cache_keys.append(f'tag_articles:{tag.pk}')
        
        for key in cache_keys:
            cache.delete(key)
    
    def get_absolute_url(self) -> str:
        """
        Возвращает абсолютный URL статьи
        """
        return reverse('article-detail', kwargs={'slug': self.slug})
    
    def increment_view_count(self):
        """
        Увеличивает счетчик просмотров
        """
        Article.objects.filter(pk=self.pk).update(
            view_count=F('view_count') + 1
        )
        self.refresh_from_db()
    
    def increment_like_count(self):
        """
        Увеличивает счетчик лайков
        """
        Article.objects.filter(pk=self.pk).update(
            like_count=F('like_count') + 1
        )
        self.refresh_from_db()
    
    def decrement_like_count(self):
        """
        Уменьшает счетчик лайков
        """
        Article.objects.filter(pk=self.pk).update(
            like_count=F('like_count') - 1
        )
        self.refresh_from_db()
    
    def update_comment_count(self):
        """
        Обновляет счетчик комментариев
        """
        count = self.comments.filter(is_approved=True).count()
        Article.objects.filter(pk=self.pk).update(comment_count=count)
        self.refresh_from_db()
    
    @property
    def is_published(self) -> bool:
        """
        Проверяет, опубликована ли статья
        """
        return self.status == self.ArticleStatus.PUBLISHED and self.published_at is not None
    
    @property
    def is_scheduled(self) -> bool:
        """
        Проверяет, запланирована ли статья
        """
        return self.scheduled_at is not None and self.scheduled_at > timezone.now()
    
    @property
    def reading_time(self) -> int:
        """
        Возвращает время чтения статьи в минутах
        """
        # Средняя скорость чтения: 200 слов в минуту
        word_count = len(self.content.split())
        return max(1, round(word_count / 200))
    
    @property
    def word_count(self) -> int:
        """
        Возвращает количество слов в статье
        """
        return len(self.content.split())
    
    def can_edit(self, user: User) -> bool:
        """
        Проверяет, может ли пользователь редактировать статью
        """
        if user.is_superuser:
            return True
        
        if user == self.author:
            return True
        
        if user.is_editor and user.has_perm('core.can_moderate'):
            return True
        
        return False
    
    def can_delete(self, user: User) -> bool:
        """
        Проверяет, может ли пользователь удалить статью
        """
        return self.can_edit(user)
    
    def get_related_articles(self, limit: int = 5) -> models.QuerySet:
        """
        Возвращает связанные статьи
        """
        from django.db.models import Count
        
        # Ищем статьи с такими же тегами
        return Article.objects.filter(
            tags__in=self.tags.all(),
            status=self.ArticleStatus.PUBLISHED,
            published_at__isnull=False
        ).exclude(
            pk=self.pk
        ).annotate(
            common_tags=Count('tags')
        ).order_by(
            '-common_tags',
            '-published_at'
        )[:limit]


class Comment(models.Model):
    """
    Модель комментария к статье
    """
    
    class CommentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        SPAM = 'spam', _('Spam')
        DELETED = 'deleted', _('Deleted')
    
    # Связи
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('article'),
        db_index=True
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('author'),
        db_index=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name=_('parent comment'),
        blank=True,
        null=True,
        db_index=True
    )
    
    # Контент
    content = models.TextField(
        _('content'),
        validators=[
            MinLengthValidator(3, message=_('Comment must be at least 3 characters long.'))
        ]
    )
    
    # Статус и модерация
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=CommentStatus.choices,
        default=CommentStatus.PENDING if settings.DEBUG else CommentStatus.APPROVED,
        db_index=True
    )
    is_edited = models.BooleanField(
        _('is edited'),
        default=False
    )
    edited_at = models.DateTimeField(
        _('edited at'),
        blank=True,
        null=True
    )
    edit_reason = models.CharField(
        _('edit reason'),
        max_length=200,
        blank=True,
        null=True
    )
    
    # Лайки
    like_count = models.PositiveIntegerField(
        _('like count'),
        default=0,
        editable=False
    )
    dislike_count = models.PositiveIntegerField(
        _('dislike count'),
        default=0,
        editable=False
    )
    
    # IP и user agent
    ip_address = models.GenericIPAddressField(
        _('IP address'),
        blank=True,
        null=True
    )
    user_agent = models.TextField(
        _('user agent'),
        blank=True,
        null=True
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )
    
    class Meta:
        verbose_name = _('comment')
        verbose_name_plural = _('comments')
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['article', 'status', 'created_at']),
            models.Index(fields=['author', 'status']),
            models.Index(fields=['parent', 'status']),
        ]
        permissions = [
            ('can_moderate_comments', 'Can moderate comments'),
            ('can_view_all_comments', 'Can view all comments'),
        ]
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.article.title}"
    
    def clean(self):
        """
        Валидация модели
        """
        super().clean()
        
        # Проверяем, что комментарий не является ответом самому себе
        if self.parent and self.parent == self:
            raise ValidationError({'parent': _('Comment cannot be a reply to itself.')})
        
        # Проверяем циклические зависимости
        if self.parent:
            current = self.parent
            while current:
                if current == self:
                    raise ValidationError({'parent': _('Circular dependency detected.')})
                current = current.parent
        
        # Проверяем, что статья позволяет комментарии
        if not self.article.allow_comments:
            raise ValidationError(_('Comments are not allowed for this article.'))
    
    def save(self, *args, **kwargs):
        """
        Переопределяем save для обработки статуса
        """
        self.clean()
        
        is_new = self.pk is None
        
        # Автоматически одобряем комментарии автора статьи
        if not is_new:
            old = Comment.objects.get(pk=self.pk)
            if self.content != old.content:
                self.is_edited = True
                self.edited_at = timezone.now()
        
        super().save(*args, **kwargs)
        
        # Обновляем счетчик комментариев в статье
        if is_new or self.status != old.status:
            self.article.update_comment_count()
    
    def get_absolute_url(self) -> str:
        """
        Возвращает абсолютный URL комментария
        """
        return reverse('comment-detail', kwargs={'pk': self.pk})
    
    def increment_like_count(self):
        """
        Увеличивает счетчик лайков
        """
        Comment.objects.filter(pk=self.pk).update(
            like_count=F('like_count') + 1
        )
        self.refresh_from_db()
    
    def decrement_like_count(self):
        """
        Уменьшает счетчик лайков
        """
        Comment.objects.filter(pk=self.pk).update(
            like_count=F('like_count') - 1
        )
        self.refresh_from_db()
    
    def increment_dislike_count(self):
        """
        Увеличивает счетчик дизлайков
        """
        Comment.objects.filter(pk=self.pk).update(
            dislike_count=F('dislike_count') + 1
        )
        self.refresh_from_db()
    
    def decrement_dislike_count(self):
        """
        Уменьшает счетчик дизлайков
        """
        Comment.objects.filter(pk=self.pk).update(
            dislike_count=F('dislike_count') - 1
        )
        self.refresh_from_db()
    
    @property
    def is_approved(self) -> bool:
        """
        Проверяет, одобрен ли комментарий
        """
        return self.status == self.CommentStatus.APPROVED
    
    @property
    def depth(self) -> int:
        """
        Возвращает глубину комментария в иерархии
        """
        depth = 0
        parent = self.parent
        while parent:
            depth += 1
            parent = parent.parent
        return depth
    
    @property
    def can_reply(self) -> bool:
        """
        Проверяет, можно ли отвечать на комментарий
        """
        return self.depth < 5  # Ограничиваем глубину вложенности
    
    def can_edit(self, user: User) -> bool:
        """
        Проверяет, может ли пользователь редактировать комментарий
        """
        if user.is_superuser:
            return True
        
        if user == self.author:
            return True
        
        if user.is_editor and user.has_perm('core.can_moderate_comments'):
            return True
        
        return False
    
    def can_delete(self, user: User) -> bool:
        """
        Проверяет, может ли пользователь удалить комментарий
        """
        return self.can_edit(user)


class Like(models.Model):
    """
    Модель лайка/дизлайка для статей и комментариев
    """
    
    class LikeType(models.TextChoices):
        LIKE = 'like', _('Like')
        DISLIKE = 'dislike', _('Dislike')
    
    # Связи
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('user'),
        db_index=True
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('article'),
        blank=True,
        null=True,
        db_index=True
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('comment'),
        blank=True,
        null=True,
        db_index=True
    )
    
    # Тип реакции
    like_type = models.CharField(
        _('type'),
        max_length=10,
        choices=LikeType.choices,
        default=LikeType.LIKE
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    
    class Meta:
        verbose_name = _('like')
        verbose_name_plural = _('likes')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'article']),
            models.Index(fields=['user', 'comment']),
            models.Index(fields=['article', 'like_type']),
            models.Index(fields=['comment', 'like_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'article'],
                name='unique_user_article_like',
                condition=Q(article__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['user', 'comment'],
                name='unique_user_comment_like',
                condition=Q(comment__isnull=False)
            ),
            models.CheckConstraint(
                check=Q(article__isnull=False) | Q(comment__isnull=False),
                name='like_must_have_target'
            ),
        ]
    
    def __str__(self):
        target = self.article.title if self.article else self.comment.content[:50]
        return f"{self.get_like_type_display()} by {self.user.username} on {target}"
    
    def clean(self):
        """
        Валидация модели
        """
        super().clean()
        
        # Проверяем, что указана либо статья, либо комментарий
        if not self.article and not self.comment:
            raise ValidationError(_('Like must be associated with either an article or a comment.'))
        
        if self.article and self.comment:
            raise ValidationError(_('Like cannot be associated with both an article and a comment.'))
    
    def save(self, *args, **kwargs):
        """
        Переопределяем save для обновления счетчиков
        """
        self.clean()
        
        is_new = self.pk is None
        
        if is_new:
            # Проверяем существующий лайк
            existing_like = None
            if self.article:
                existing_like = Like.objects.filter(
                    user=self.user,
                    article=self.article
                ).first()
            elif self.comment:
                existing_like = Like.objects.filter(
                    user=self.user,
                    comment=self.comment
                ).first()
            
            if existing_like:
                # Если тип тот же - удаляем
                if existing_like.like_type == self.like_type:
                    existing_like.delete()
                    self.pk = None  # Отменяем сохранение
                    return
                else:
                    # Если тип другой - меняем
                    existing_like.like_type = self.like_type
                    existing_like.save()
                    self.pk = existing_like.pk
                    return
        
        super().save(*args, **kwargs)
        
        # Обновляем счетчики
        self.update_counters()
    
    def update_counters(self):
        """
        Обновляет счетчики лайков/дизлайков
        """
        if self.article:
            if self.like_type == self.LikeType.LIKE:
                self.article.increment_like_count()
            # Для статей обычно не считаем дизлайки
        elif self.comment:
            if self.like_type == self.LikeType.LIKE:
                self.comment.increment_like_count()
            else:
                self.comment.increment_dislike_count()
    
    def delete(self, *args, **kwargs):
        """
        Переопределяем удаление для обновления счетчиков
        """
        target = self.article or self.comment
        
        super().delete(*args, **kwargs)
        
        # Обновляем счетчики
        if self.article and self.like_type == self.LikeType.LIKE:
            self.article.decrement_like_count()
        elif self.comment:
            if self.like_type == self.LikeType.LIKE:
                self.comment.decrement_like_count()
            else:
                self.comment.decrement_dislike_count()


class Bookmark(models.Model):
    """
    Модель закладки для статей
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookmarks',
        verbose_name=_('user'),
        db_index=True
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='bookmarks',
        verbose_name=_('article'),
        db_index=True
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    
    class Meta:
        verbose_name = _('bookmark')
        verbose_name_plural = _('bookmarks')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'article']),
            models.Index(fields=['user', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'article'],
                name='unique_user_article_bookmark'
            )
        ]
    
    def __str__(self):
        return f"Bookmark: {self.user.username} -> {self.article.title}"
    
    def clean(self):
        """
        Валидация модели
        """
        super().clean()
        
        # Проверяем, что статья опубликована
        if not self.article.is_published:
            raise ValidationError(_('Cannot bookmark unpublished articles.'))


class ViewHistory(models.Model):
    """
    Модель истории просмотров статей
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='view_history',
        verbose_name=_('user'),
        db_index=True
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='view_history',
        verbose_name=_('article'),
        db_index=True
    )
    
    # Детали просмотра
    view_duration = models.PositiveIntegerField(
        _('view duration'),
        default=0,
        help_text=_('Duration in seconds')
    )
    ip_address = models.GenericIPAddressField(
        _('IP address'),
        blank=True,
        null=True
    )
    user_agent = models.TextField(
        _('user agent'),
        blank=True,
        null=True
    )
    referrer = models.URLField(
        _('referrer'),
        max_length=500,
        blank=True,
        null=True
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    
    class Meta:
        verbose_name = _('view history')
        verbose_name_plural = _('view history')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'article', 'created_at']),
            models.Index(fields=['article', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'article', 'created_at__date'],
                name='unique_user_article_view_per_day'
            )
        ]
    
    def __str__(self):
        return f"View: {self.user.username} -> {self.article.title}"


# Сигналы для обновления счетчиков
@receiver(post_save, sender=Article)
def update_category_article_count(sender, instance, created, **kwargs):
    """
    Обновляет счетчик статей в категории при сохранении статьи
    """
    if instance.category:
        instance.category.update_article_count()


@receiver(post_save, sender=Article)
def update_tag_usage_count(sender, instance, created, **kwargs):
    """
    Обновляет счетчик использования тегов при сохранении статьи
    """
    for tag in instance.tags.all():
        tag.update_usage_count()


@receiver(post_save, sender=Comment)
def send_comment_notification(sender, instance, created, **kwargs):
    """
    Отправляет уведомление о новом комментарии
    """
    if created and instance.is_approved:
        from core.tasks import send_comment_notification_email
        send_comment_notification_email.delay(instance.pk)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Создает профиль пользователя при создании пользователя
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Сохраняет профиль пользователя
    """
    instance.profile.save()


@receiver(post_delete, sender=Article)
def cleanup_article_files(sender, instance, **kwargs):
    """
    Удаляет файлы статьи при удалении статьи
    """
    if instance.featured_image:
        instance.featured_image.delete(save=False)


@receiver(post_delete, sender=User)
def cleanup_user_files(sender, instance, **kwargs):
    """
    Удаляет файлы пользователя при удалении пользователя
    """
    if instance.avatar:
        instance.avatar.delete(save=False)
