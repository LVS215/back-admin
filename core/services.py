"""
Сервисный слой приложения - содержит бизнес-логику
"""

from django.db import transaction
from django.db.models import Q, F, Count, Sum, Avg, Max, Min
from django.utils import timezone
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.text import slugify
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging
import secrets
import hashlib

from .models import (
    User, UserProfile, Category, Tag, Article, Comment,
    Like, Bookmark, ViewHistory
)
from .logging_config import logger, log_operation


class BaseService:
    """
    Базовый сервис с общими методами
    """
    
    @staticmethod
    def get_cache_key(prefix: str, **kwargs) -> str:
        """
        Генерирует ключ кэша
        """
        parts = [prefix]
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        return ":".join(parts)
    
    @staticmethod
    def invalidate_cache(prefix: str, **kwargs):
        """
        Инвалидирует кэш по префиксу
        """
        pattern = f"{prefix}:*"
        keys = cache.keys(pattern)
        if keys:
            cache.delete_many(keys)


class AuthService(BaseService):
    """
    Сервис аутентификации и авторизации
    """
    
    @staticmethod
    @log_operation("register_user")
    def register_user(
        username: str,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        **extra_fields
    ) -> User:
        """
        Регистрация нового пользователя
        """
        with transaction.atomic():
            # Проверяем уникальность email
            if User.objects.filter(email=email).exists():
                raise ValidationError("User with this email already exists")
            
            # Проверяем уникальность username
            if User.objects.filter(username=username).exists():
                raise ValidationError("User with this username already exists")
            
            # Создаем пользователя
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                **extra_fields
            )
            
            # Создаем профиль пользователя
            UserProfile.objects.create(user=user)
            
            # Генерируем verification token
            user.verification_token = secrets.token_hex(32)
            user.verification_sent_at = timezone.now()
            user.save(update_fields=['verification_token', 'verification_sent_at'])
            
            # Отправляем email для верификации
            AuthService.send_verification_email(user)
            
            logger.info(
                "user_registered",
                user_id=user.id,
                username=username,
                email=email
            )
            
            return user
    
    @staticmethod
    @log_operation("send_verification_email")
    def send_verification_email(user: User) -> bool:
        """
        Отправляет email для верификации
        """
        try:
            subject = "Verify your email address"
            context = {
                'user': user,
                'verification_url': f"{settings.FRONTEND_URL}/verify-email/{user.verification_token}",
                'site_name': settings.SITE_NAME
            }
            html_message = render_to_string('emails/verification.html', context)
            plain_message = render_to_string('emails/verification.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info("verification_email_sent", user_id=user.id, email=user.email)
            return True
            
        except Exception as e:
            logger.error("verification_email_failed", user_id=user.id, error=str(e))
            return False
    
    @staticmethod
    @log_operation("verify_email")
    def verify_email(token: str) -> Tuple[bool, Optional[User]]:
        """
        Верифицирует email пользователя по токену
        """
        try:
            user = User.objects.get(verification_token=token)
            
            # Проверяем, не истек ли токен (24 часа)
            token_age = timezone.now() - user.verification_sent_at
            if token_age > timedelta(hours=24):
                logger.warning("verification_token_expired", user_id=user.id)
                return False, user
            
            # Верифицируем email
            user.email_verified = True
            user.verification_token = None
            user.verification_sent_at = None
            user.save(update_fields=['email_verified', 'verification_token', 'verification_sent_at'])
            
            logger.info("email_verified", user_id=user.id)
            return True, user
            
        except User.DoesNotExist:
            logger.warning("verification_token_invalid", token=token)
            return False, None
    
    @staticmethod
    @log_operation("send_password_reset_email")
    def send_password_reset_email(email: str) -> bool:
        """
        Отправляет email для сброса пароля
        """
        try:
            user = User.objects.get(email=email, is_active=True)
            
            # Генерируем токен сброса пароля
            reset_token = secrets.token_hex(32)
            user.verification_token = reset_token
            user.verification_sent_at = timezone.now()
            user.save(update_fields=['verification_token', 'verification_sent_at'])
            
            # Отправляем email
            subject = "Password reset request"
            context = {
                'user': user,
                'reset_url': f"{settings.FRONTEND_URL}/reset-password/{reset_token}",
                'site_name': settings.SITE_NAME
            }
            html_message = render_to_string('emails/password_reset.html', context)
            plain_message = render_to_string('emails/password_reset.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info("password_reset_email_sent", user_id=user.id, email=email)
            return True
            
        except User.DoesNotExist:
            logger.warning("password_reset_user_not_found", email=email)
            return False
        except Exception as e:
            logger.error("password_reset_email_failed", email=email, error=str(e))
            return False
    
    @staticmethod
    @log_operation("reset_password")
    def reset_password(token: str, new_password: str) -> Tuple[bool, Optional[User]]:
        """
        Сбрасывает пароль пользователя
        """
        try:
            user = User.objects.get(verification_token=token, is_active=True)
            
            # Проверяем, не истек ли токен (1 час)
            token_age = timezone.now() - user.verification_sent_at
            if token_age > timedelta(hours=1):
                logger.warning("password_reset_token_expired", user_id=user.id)
                return False, user
            
            # Устанавливаем новый пароль
            user.set_password(new_password)
            user.verification_token = None
            user.verification_sent_at = None
            user.save(update_fields=['password', 'verification_token', 'verification_sent_at'])
            
            logger.info("password_reset_successful", user_id=user.id)
            return True, user
            
        except User.DoesNotExist:
            logger.warning("password_reset_token_invalid", token=token)
            return False, None


class CategoryService(BaseService):
    """
    Сервис для работы с категориями
    """
    
    @staticmethod
    @log_operation("create_category")
    def create_category(
        name: str,
        description: Optional[str] = None,
        parent_id: Optional[int] = None,
        color: str = '#6c757d',
        icon: Optional[str] = None,
        is_active: bool = True,
        show_in_menu: bool = True,
        sort_order: int = 0,
        meta_title: Optional[str] = None,
        meta_description: Optional[str] = None,
        created_by: Optional[User] = None
    ) -> Category:
        """
        Создает новую категорию
        """
        with transaction.atomic():
            # Проверяем уникальность имени
            if Category.objects.filter(name=name).exists():
                raise ValidationError("Category with this name already exists")
            
            # Проверяем parent_id
            parent = None
            if parent_id:
                try:
                    parent = Category.objects.get(id=parent_id)
                except Category.DoesNotExist:
                    raise ValidationError("Parent category does not exist")
            
            # Генерируем slug
            base_slug = slugify(name, allow_unicode=True)
            slug = base_slug
            counter = 1
            
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            # Создаем категорию
            category = Category.objects.create(
                name=name,
                slug=slug,
                description=description,
                parent=parent,
                color=color,
                icon=icon,
                is_active=is_active,
                show_in_menu=show_in_menu,
                sort_order=sort_order,
                meta_title=meta_title or name,
                meta_description=meta_description,
                created_by=created_by
            )
            
            # Инвалидируем кэш категорий
            CategoryService.invalidate_cache('categories')
            
            logger.info(
                "category_created",
                category_id=category.id,
                name=name,
                slug=slug
            )
            
            return category
    
    @staticmethod
    @log_operation("update_category")
    def update_category(category: Category, **kwargs) -> Category:
        """
        Обновляет категорию
        """
        with transaction.atomic():
            # Проверяем изменение имени
            if 'name' in kwargs and kwargs['name'] != category.name:
                # Проверяем уникальность нового имени
                if Category.objects.filter(name=kwargs['name']).exclude(id=category.id).exists():
                    raise ValidationError("Category with this name already exists")
                
                # Генерируем новый slug
                base_slug = slugify(kwargs['name'], allow_unicode=True)
                slug = base_slug
                counter = 1
                
                while Category.objects.filter(slug=slug).exclude(id=category.id).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                kwargs['slug'] = slug
            
            # Проверяем изменение parent_id
            if 'parent_id' in kwargs:
                parent_id = kwargs.pop('parent_id')
                parent = None
                
                if parent_id:
                    try:
                        parent = Category.objects.get(id=parent_id)
                        if parent == category:
                            raise ValidationError("Category cannot be parent of itself")
                        
                        # Проверяем циклические зависимости
                        current = parent
                        while current:
                            if current == category:
                                raise ValidationError("Circular dependency detected")
                            current = current.parent
                        
                        kwargs['parent'] = parent
                    except Category.DoesNotExist:
                        raise ValidationError("Parent category does not exist")
                else:
                    kwargs['parent'] = None
            
            # Обновляем поля
            for field, value in kwargs.items():
                if value is not None:
                    setattr(category, field, value)
            
            category.save()
            
            # Инвалидируем кэш категорий
            CategoryService.invalidate_cache('categories')
            
            logger.info("category_updated", category_id=category.id)
            
            return category
    
    @staticmethod
    @log_operation("delete_category")
    def delete_category(category: Category) -> bool:
        """
        Удаляет категорию
        """
        # Проверяем, есть ли дочерние категории
        if category.children.exists():
            raise ValidationError("Cannot delete category with children")
        
        # Проверяем, есть ли статьи в категории
        if category.articles.exists():
            raise ValidationError("Cannot delete category with articles")
        
        with transaction.atomic():
            category.delete()
            
            # Инвалидируем кэш категорий
            CategoryService.invalidate_cache('categories')
            
            logger.info("category_deleted", category_id=category.id)
            
            return True
    
    @staticmethod
    @log_operation("get_category_tree")
    def get_category_tree(include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Возвращает дерево категорий
        """
        cache_key = CategoryService.get_cache_key(
            'category_tree',
            include_inactive=include_inactive
        )
        
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        
        queryset = Category.objects.all()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        
        categories = list(queryset.order_by('sort_order', 'name'))
        
        # Строим дерево
        category_dict = {}
        tree = []
        
        # Создаем словарь категорий
        for category in categories:
            category_dict[category.id] = {
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'description': category.description,
                'color': category.color,
                'icon': category.icon,
                'is_active': category.is_active,
                'show_in_menu': category.show_in_menu,
                'sort_order': category.sort_order,
                'article_count': category.article_count,
                'children': []
            }
        
        # Строим иерархию
        for category in categories:
            if category.parent_id is None:
                tree.append(category_dict[category.id])
            else:
                parent = category_dict.get(category.parent_id)
                if parent:
                    parent['children'].append(category_dict[category.id])
        
        # Сортируем детей
        for item in category_dict.values():
            item['children'].sort(key=lambda x: (x['sort_order'], x['name']))
        
        tree.sort(key=lambda x: (x['sort_order'], x['name']))
        
        # Кэшируем на 1 час
        cache.set(cache_key, tree, 3600)
        
        return tree


class ArticleService(BaseService):
    """
    Сервис для работы со статьями
    """
    
    @staticmethod
    @log_operation("create_article")
    def create_article(
        author: User,
        title: str,
        content: str,
        excerpt: Optional[str] = None,
        category_id: Optional[int] = None,
        tag_ids: Optional[List[int]] = None,
        status: str = 'draft',
        article_type: str = 'article',
        featured_image: Optional[str] = None,
        image_caption: Optional[str] = None,
        meta_title: Optional[str] = None,
        meta_description: Optional[str] = None,
        canonical_url: Optional[str] = None,
        is_featured: bool = False,
        is_pinned: bool = False,
        allow_comments: bool = True,
        allow_sharing: bool = True,
        require_login: bool = False,
        scheduled_at: Optional[datetime] = None
    ) -> Article:
        """
        Создает новую статью
        """
        with transaction.atomic():
            # Проверяем права доступа
            if not author.is_author:
                raise PermissionDenied("You don't have permission to create articles")
            
            # Проверяем категорию
            category = None
            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
                    raise ValidationError("Category does not exist")
            
            # Проверяем теги
            tags = []
            if tag_ids:
                tags = list(Tag.objects.filter(id__in=tag_ids))
                if len(tags) != len(tag_ids):
                    raise ValidationError("Some tags do not exist")
            
            # Проверяем scheduled публикацию
            if scheduled_at:
                if scheduled_at <= timezone.now():
                    raise ValidationError("Scheduled date must be in the future")
                if status != 'draft':
                    raise ValidationError("Scheduled articles must be in draft status")
            
            # Генерируем slug
            base_slug = slugify(title, allow_unicode=True)
            slug = base_slug
            counter = 1
            
            while Article.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            # Создаем статью
            article = Article.objects.create(
                title=title,
                slug=slug,
                content=content,
                excerpt=excerpt,
                author=author,
                category=category,
                status=status,
                article_type=article_type,
                featured_image=featured_image,
                image_caption=image_caption,
                meta_title=meta_title or title,
                meta_description=meta_description,
                canonical_url=canonical_url,
                is_featured=is_featured,
                is_pinned=is_pinned,
                allow_comments=allow_comments,
                allow_sharing=allow_sharing,
                require_login=require_login,
                published_at=timezone.now() if status == 'published' else None,
                scheduled_at=scheduled_at,
                last_edited_by=author,
                last_edited_at=timezone.now()
            )
            
            # Добавляем теги
            if tags:
                article.tags.set(tags)
            
            # Инвалидируем кэш статей
            ArticleService.invalidate_cache('articles')
            
            logger.info(
                "article_created",
                article_id=article.id,
                title=title,
                author_id=author.id,
                status=status
            )
            
            return article
    
    @staticmethod
    @log_operation("update_article")
    def update_article(article: Article, editor: User, **kwargs) -> Article:
        """
        Обновляет статью
        """
        with transaction.atomic():
            # Проверяем права доступа
            if not article.can_edit(editor):
                raise PermissionDenied("You don't have permission to edit this article")
            
            # Проверяем изменение заголовка
            if 'title' in kwargs and kwargs['title'] != article.title:
                # Генерируем новый slug
                base_slug = slugify(kwargs['title'], allow_unicode=True)
                slug = base_slug
                counter = 1
                
                while Article.objects.filter(slug=slug).exclude(id=article.id).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                kwargs['slug'] = slug
            
            # Проверяем категорию
            if 'category_id' in kwargs:
                category_id = kwargs.pop('category_id')
                category = None
                
                if category_id:
                    try:
                        category = Category.objects.get(id=category_id)
                        kwargs['category'] = category
                    except Category.DoesNotExist:
                        raise ValidationError("Category does not exist")
                else:
                    kwargs['category'] = None
            
            # Проверяем теги
            if 'tag_ids' in kwargs:
                tag_ids = kwargs.pop('tag_ids')
                tags = []
                
                if tag_ids:
                    tags = list(Tag.objects.filter(id__in=tag_ids))
                    if len(tags) != len(tag_ids):
                        raise ValidationError("Some tags do not exist")
                
                article.tags.set(tags)
            
            # Проверяем изменение статуса
            if 'status' in kwargs:
                new_status = kwargs['status']
                
                if new_status == 'published' and article.status != 'published':
                    kwargs['published_at'] = timezone.now()
                
                if new_status != 'published' and article.status == 'published':
                    kwargs['published_at'] = None
            
            # Проверяем scheduled публикацию
            if 'scheduled_at' in kwargs:
                scheduled_at = kwargs['scheduled_at']
                
                if scheduled_at:
                    if scheduled_at <= timezone.now():
                        raise ValidationError("Scheduled date must be in the future")
                    if kwargs.get('status', article.status) != 'draft':
                        raise ValidationError("Scheduled articles must be in draft status")
            
            # Обновляем поля
            for field, value in kwargs.items():
                if value is not None:
                    setattr(article, field, value)
            
            # Обновляем метаданные редактирования
            article.last_edited_by = editor
            article.last_edited_at = timezone.now()
            
            article.save()
            
            # Инвалидируем кэш статей
            ArticleService.invalidate_cache('articles')
            
            logger.info(
                "article_updated",
                article_id=article.id,
                editor_id=editor.id
            )
            
            return article
    
    @staticmethod
    @log_operation("delete_article")
    def delete_article(article: Article) -> bool:
        """
        Удаляет статью
        """
        with transaction.atomic():
            article_id = article.id
            article_title = article.title
            
            article.delete()
            
            # Инвалидируем кэш статей
            ArticleService.invalidate_cache('articles')
            
            logger.info(
                "article_deleted",
                article_id=article_id,
                title=article_title
            )
            
            return True
    
    @staticmethod
    @log_operation("increment_view_count")
    def increment_view_count(article: Article, request) -> None:
        """
        Увеличивает счетчик просмотров статьи
        """
        with transaction.atomic():
            # Увеличиваем счетчик в статье
            Article.objects.filter(id=article.id).update(
                view_count=F('view_count') + 1
            )
            
            # Записываем в историю просмотров
            if request.user.is_authenticated:
                ViewHistory.objects.create(
                    user=request.user,
                    article=article,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT'),
                    referrer=request.META.get('HTTP_REFERER')
                )
            
            # Инвалидируем кэш популярных статей
            cache.delete_pattern('popular_articles:*')
    
    @staticmethod
    @log_operation("get_featured_articles")
    def get_featured_articles(limit: int = 5) -> List[Article]:
        """
        Возвращает список рекомендуемых статей
        """
        cache_key = ArticleService.get_cache_key('featured_articles', limit=limit)
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        articles = Article.objects.filter(
            status='published',
            is_featured=True,
            published_at__isnull=False
        ).select_related(
            'author', 'category'
        ).prefetch_related(
            'tags'
        ).order_by(
            '-published_at'
        )[:limit]
        
        articles_list = list(articles)
        
        # Кэшируем на 1 час
        cache.set(cache_key, articles_list, 3600)
        
        return articles_list
    
    @staticmethod
    @log_operation("get_popular_articles")
    def get_popular_articles(limit: int = 10) -> List[Article]:
        """
        Возвращает список популярных статей
        """
        cache_key = ArticleService.get_cache_key('popular_articles', limit=limit)
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        articles = Article.objects.filter(
            status='published',
            published_at__isnull=False
        ).select_related(
            'author', 'category'
        ).prefetch_related(
            'tags'
        ).order_by(
            '-view_count',
            '-published_at'
        )[:limit]
        
        articles_list = list(articles)
        
        # Кэшируем на 30 минут
        cache.set(cache_key, articles_list, 1800)
        
        return articles_list
    
    @staticmethod
    @log_operation("publish_scheduled_articles")
    def publish_scheduled_articles() -> int:
        """
        Публикует запланированные статьи
        """
        now = timezone.now()
        scheduled_articles = Article.objects.filter(
            status='draft',
            scheduled_at__lte=now,
            scheduled_at__isnull=False
        )
        
        count = scheduled_articles.count()
        
        with transaction.atomic():
            scheduled_articles.update(
                status='published',
                published_at=F('scheduled_at'),
                scheduled_at=None,
                updated_at=now
            )
        
        if count > 0:
            # Инвалидируем кэш статей
            ArticleService.invalidate_cache('articles')
            
            logger.info(
                "scheduled_articles_published",
                count=count,
                timestamp=now
            )
        
        return count


class CommentService(BaseService):
    """
    Сервис для работы с комментариями
    """
    
    @staticmethod
    @log_operation("create_comment")
    def create_comment(
        author: User,
        article: Article,
        content: str,
        parent_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Comment:
        """
        Создает новый комментарий
        """
        with transaction.atomic():
            # Проверяем, разрешены ли комментарии
            if not article.allow_comments:
                raise ValidationError("Comments are not allowed for this article")
            
            # Проверяем родительский комментарий
            parent = None
            if parent_id:
                try:
                    parent = Comment.objects.get(id=parent_id, article=article)
                    
                    # Проверяем глубину вложенности
                    if parent.depth >= 5:
                        raise ValidationError("Maximum comment depth reached")
                except Comment.DoesNotExist:
                    raise ValidationError("Parent comment does not exist or belongs to different article")
            
            # Определяем статус комментария
            status = 'approved'
            if not author.is_verified:
                status = 'pending'  # Модерация для неверифицированных пользователей
            
            # Создаем комментарий
            comment = Comment.objects.create(
                article=article,
                author=author,
                parent=parent,
                content=content,
                status=status,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Обновляем счетчик комментариев в статье
            if status == 'approved':
                Article.objects.filter(id=article.id).update(
                    comment_count=F('comment_count') + 1
                )
                article.refresh_from_db()
            
            logger.info(
                "comment_created",
                comment_id=comment.id,
                article_id=article.id,
                author_id=author.id,
                status=status
            )
            
            return comment
    
    @staticmethod
    @log_operation("update_comment")
    def update_comment(
        comment: Comment,
        content: str,
        edit_reason: Optional[str] = None
    ) -> Comment:
        """
        Обновляет комментарий
        """
        with transaction.atomic():
            comment.content = content
            comment.is_edited = True
            comment.edited_at = timezone.now()
            comment.edit_reason = edit_reason
            comment.save()
            
            logger.info("comment_updated", comment_id=comment.id)
            
            return comment
    
    @staticmethod
    @log_operation("delete_comment")
    def delete_comment(comment: Comment) -> bool:
        """
        Удаляет комментарий
        """
        with transaction.atomic():
            article_id = comment.article_id
            was_approved = comment.is_approved
            
            comment.delete()
            
            # Обновляем счетчик комментариев в статье
            if was_approved:
                Article.objects.filter(id=article_id).update(
                    comment_count=F('comment_count') - 1
                )
            
            logger.info("comment_deleted", comment_id=comment.id)
            
            return True
    
    @staticmethod
    @log_operation("moderate_comment")
    def moderate_comment(comment: Comment, action: str, moderator: User) -> Comment:
        """
        Модерирует комментарий (одобрить/отклонить/пометить как спам)
        """
        valid_actions = ['approve', 'reject', 'spam']
        if action not in valid_actions:
            raise ValidationError(f"Invalid action. Use: {', '.join(valid_actions)}")
        
        with transaction.atomic():
            old_status = comment.status
            article_id = comment.article_id
            
            if action == 'approve':
                comment.status = 'approved'
            elif action == 'reject':
                comment.status = 'pending'
            elif action == 'spam':
                comment.status = 'spam'
            
            comment.save()
            
            # Обновляем счетчик комментариев в статье
            if old_status == 'approved' and comment.status != 'approved':
                # Уменьшаем счетчик
                Article.objects.filter(id=article_id).update(
                    comment_count=F('comment_count') - 1
                )
            elif old_status != 'approved' and comment.status == 'approved':
                # Увеличиваем счетчик
                Article.objects.filter(id=article_id).update(
                    comment_count=F('comment_count') + 1
                )
            
            logger.info(
                "comment_moderated",
                comment_id=comment.id,
                action=action,
                moderator_id=moderator.id,
                old_status=old_status,
                new_status=comment.status
            )
            
            return comment


class LikeService(BaseService):
    """
    Сервис для работы с лайками
    """
    
    @staticmethod
    @log_operation("toggle_like")
    def toggle_like(
        user: User,
        article: Optional[Article] = None,
        comment: Optional[Comment] = None,
        like_type: str = 'like'
    ) -> str:
        """
        Переключает лайк/дизлайк
        """
        if like_type not in ['like', 'dislike']:
            raise ValidationError("Invalid like type. Use 'like' or 'dislike'")
        
        if not article and not comment:
            raise ValidationError("Either article or comment must be specified")
        
        if article and comment:
            raise ValidationError("Cannot like both article and comment at the same time")
        
        with transaction.atomic():
            # Ищем существующий лайк
            like = None
            if article:
                like = Like.objects.filter(user=user, article=article).first()
            elif comment:
                like = Like.objects.filter(user=user, comment=comment).first()
            
            if like:
                # Если тип тот же - удаляем
                if like.like_type == like_type:
                    like.delete()
                    action = 'removed'
                else:
                    # Если тип другой - меняем
                    old_type = like.like_type
                    like.like_type = like_type
                    like.save()
                    
                    # Обновляем счетчики
                    LikeService._update_counters(article, comment, old_type, like_type)
                    action = 'changed'
            else:
                # Создаем новый лайк
                Like.objects.create(
                    user=user,
                    article=article,
                    comment=comment,
                    like_type=like_type
                )
                
                # Обновляем счетчики
                LikeService._update_counters(article, comment, None, like_type)
                action = 'added'
            
            logger.info(
                "like_toggled",
                user_id=user.id,
                target_type="article" if article else "comment",
                target_id=article.id if article else comment.id,
                like_type=like_type,
                action=action
            )
            
            return action
    
    @staticmethod
    def _update_counters(
        article: Optional[Article],
        comment: Optional[Comment],
        old_type: Optional[str],
        new_type: str
    ) -> None:
        """
        Обновляет счетчики лайков/дизлайков
        """
        if article:
            if old_type == 'like' and new_type == 'dislike':
                # like -> dislike
                Article.objects.filter(id=article.id).update(
                    like_count=F('like_count') - 1
                )
            elif old_type == 'dislike' and new_type == 'like':
                # dislike -> like
                Article.objects.filter(id=article.id).update(
                    like_count=F('like_count') + 1
                )
            elif old_type is None and new_type == 'like':
                # новый like
                Article.objects.filter(id=article.id).update(
                    like_count=F('like_count') + 1
                )
            elif old_type == 'like' and new_type is None:
                # удаление like
                Article.objects.filter(id=article.id).update(
                    like_count=F('like_count') - 1
                )
        elif comment:
            if old_type == 'like' and new_type == 'dislike':
                # like -> dislike
                Comment.objects.filter(id=comment.id).update(
                    like_count=F('like_count') - 1,
                    dislike_count=F('dislike_count') + 1
                )
            elif old_type == 'dislike' and new_type == 'like':
                # dislike -> like
                Comment.objects.filter(id=comment.id).update(
                    like_count=F('like_count') + 1,
                    dislike_count=F('dislike_count') - 1
                )
            elif old_type is None:
                if new_type == 'like':
                    # новый like
                    Comment.objects.filter(id=comment.id).update(
                        like_count=F('like_count') + 1
                    )
                elif new_type == 'dislike':
                    # новый dislike
                    Comment.objects.filter(id=comment.id).update(
                        dislike_count=F('dislike_count') + 1
                    )
            elif new_type is None:
                if old_type == 'like':
                    # удаление like
                    Comment.objects.filter(id=comment.id).update(
                        like_count=F('like_count') - 1
                    )
                elif old_type == 'dislike':
                    # удаление dislike
                    Comment.objects.filter(id=comment.id).update(
                        dislike_count=F('dislike_count') - 1
                    )


class BookmarkService(BaseService):
    """
    Сервис для работы с закладками
    """
    
    @staticmethod
    @log_operation("toggle_bookmark")
    def toggle_bookmark(user: User, article: Article) -> Optional[Bookmark]:
        """
        Переключает закладку
        """
        with transaction.atomic():
            bookmark = Bookmark.objects.filter(user=user, article=article).first()
            
            if bookmark:
                bookmark.delete()
                logger.info(
                    "bookmark_removed",
                    user_id=user.id,
                    article_id=article.id
                )
                return None
            else:
                bookmark = Bookmark.objects.create(user=user, article=article)
                logger.info(
                    "bookmark_added",
                    bookmark_id=bookmark.id,
                    user_id=user.id,
                    article_id=article.id
                )
                return bookmark
    
    @staticmethod
    @log_operation("get_user_bookmarks")
    def get_user_bookmarks(user: User) -> List[Bookmark]:
        """
        Возвращает закладки пользователя
        """
        return list(
            Bookmark.objects.filter(user=user)
            .select_related('article', 'article__author', 'article__category')
            .prefetch_related('article__tags')
            .order_by('-created_at')
        )


class SearchService(BaseService):
    """
    Сервис для поиска
    """
    
    @staticmethod
    @log_operation("search_articles")
    def search_articles(
        query: str,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        status: Optional[str] = 'published',
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        ordering: Optional[str] = '-published_at'
    ) -> List[Article]:
        """
        Ищет статьи по заданным критериям
        """
        queryset = Article.objects.select_related(
            'author', 'category'
        ).prefetch_related(
            'tags'
        )
        
        # Фильтрация по статусу
        if status:
            queryset = queryset.filter(status=status)
        
        # Поиск по тексту
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(content__icontains=query) |
                Q(excerpt__icontains=query)
            )
        
        # Фильтрация по категории
        if category:
            if category.isdigit():
                queryset = queryset.filter(category_id=int(category))
            else:
                queryset = queryset.filter(category__slug=category)
        
        # Фильтрация по тегу
        if tag:
            if tag.isdigit():
                queryset = queryset.filter(tags__id=int(tag))
            else:
                queryset = queryset.filter(tags__slug=tag)
        
        # Фильтрация по автору
        if author:
            if author.isdigit():
                queryset = queryset.filter(author_id=int(author))
            else:
                queryset = queryset.filter(author__username=author)
        
        # Фильтрация по дате
        if date_from:
            queryset = queryset.filter(published_at__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(published_at__lte=date_to)
        
        # Сортировка
        if ordering:
            queryset = queryset.order_by(ordering)
        
        return queryset


class StatisticsService(BaseService):
    """
    Сервис для сбора статистики
    """
    
    @staticmethod
    @log_operation("get_blog_statistics")
    def get_blog_statistics() -> Dict[str, Any]:
        """
        Возвращает статистику блога
        """
        cache_key = 'blog_statistics'
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        statistics = {
            # Общая статистика
            'total_articles': Article.objects.filter(status='published').count(),
            'total_users': User.objects.filter(is_active=True).count(),
            'total_comments': Comment.objects.filter(status='approved').count(),
            'total_categories': Category.objects.filter(is_active=True).count(),
            'total_tags': Tag.objects.count(),
            
            # Статистика за последние 7 дней
            'recent_articles': Article.objects.filter(
                status='published',
                published_at__gte=week_ago
            ).count(),
            
            'recent_users': User.objects.filter(
                is_active=True,
                date_joined__gte=week_ago
            ).count(),
            
            'recent_comments': Comment.objects.filter(
                status='approved',
                created_at__gte=week_ago
            ).count(),
            
            # Популярные статьи
            'popular_articles': list(
                Article.objects.filter(status='published')
                .select_related('author', 'category')
                .order_by('-view_count')[:10]
                .values('id', 'title', 'view_count', 'like_count', 'author__username')
            ),
            
            # Недавние статьи
            'recent_articles_list': list(
                Article.objects.filter(status='published')
                .select_related('author', 'category')
                .order_by('-published_at')[:10]
                .values('id', 'title', 'published_at', 'author__username')
            ),
            
            # Активные пользователи
            'active_users': list(
                User.objects.filter(is_active=True)
                .annotate(
                    article_count=Count('articles', filter=Q(articles__status='published')),
                    comment_count=Count('comments', filter=Q(comments__status='approved'))
                )
                .order_by('-last_activity')[:10]
                .values('id', 'username', 'email', 'last_activity', 'article_count', 'comment_count')
            ),
            
            # Статистика по категориям
            'categories_stats': list(
                Category.objects.filter(is_active=True)
                .annotate(
                    article_count=Count('articles', filter=Q(articles__status='published'))
                )
                .order_by('-article_count')[:10]
                .values('id', 'name', 'article_count')
            ),
            
            # Статистика по тегам
            'tags_stats': list(
                Tag.objects.annotate(
                    usage_count=Count('articles', filter=Q(articles__status='published'))
                )
                .order_by('-usage_count')[:10]
                .values('id', 'name', 'usage_count')
            ),
            
            # Временные метки
            'generated_at': now.isoformat(),
            'time_range': {
                'today': today.isoformat(),
                'week_ago': week_ago.isoformat(),
                'month_ago': month_ago.isoformat()
            }
        }
        
        # Кэшируем на 5 минут
        cache.set(cache_key, statistics, 300)
        
        return statistics
    
    @staticmethod
    @log_operation("get_user_statistics")
    def get_user_statistics(user_id: int) -> Dict[str, Any]:
        """
        Возвращает статистику пользователя
        """
        cache_key = StatisticsService.get_cache_key('user_statistics', user_id=user_id)
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError("User does not exist")
        
        statistics = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            
            # Статистика статей
            'total_articles': user.articles.filter(status='published').count(),
            'draft_articles': user.articles.filter(status='draft').count(),
            'published_articles': user.articles.filter(status='published').count(),
            'archived_articles': user.articles.filter(status='archived').count(),
            
            # Статистика комментариев
            'total_comments': user.comments.filter(status='approved').count(),
            'pending_comments': user.comments.filter(status='pending').count(),
            'approved_comments': user.comments.filter(status='approved').count(),
            
            # Статистика лайков
            'articles_liked': Like.objects.filter(
                user=user,
                article__isnull=False
            ).count(),
            
            'comments_liked': Like.objects.filter(
                user=user,
                comment__isnull=False
            ).count(),
            
            # Статистика закладок
            'bookmarks_count': Bookmark.objects.filter(user=user).count(),
            
            # Вовлеченность
            'total_views': Article.objects.filter(
                author=user,
                status='published'
            ).aggregate(total=Sum('view_count'))['total'] or 0,
            
            'total_likes_received': Article.objects.filter(
                author=user,
                status='published'
            ).aggregate(total=Sum('like_count'))['total'] or 0,
            
            'total_comments_received': Article.objects.filter(
                author=user,
                status='published'
            ).aggregate(total=Sum('comment_count'))['total'] or 0,
            
            # Активность
            'last_article_date': user.articles.filter(
                status='published'
            ).aggregate(last=Max('published_at'))['last'],
            
            'last_comment_date': user.comments.filter(
                status='approved'
            ).aggregate(last=Max('created_at'))['last'],
            
            'generated_at': timezone.now().isoformat()
        }
        
        # Кэшируем на 10 минут
        cache.set(cache_key, statistics, 600)
        
        return statistics
