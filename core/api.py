from ninja import NinjaAPI, Router, Query
from ninja.pagination import paginate, PageNumberPagination
from ninja.security import HttpBearer
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, F, Sum, Avg, Max, Min
from django.utils import timezone
from django.core.cache import cache
from django.http import HttpRequest
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import RefreshToken
from ninja_jwt.controller import TokenObtainPairController, TokenRefreshController

from .models import (
    User, UserProfile, Category, Tag, Article, Comment,
    Like, Bookmark, ViewHistory
)
from .schemas import (
    # User schemas
    UserBase, UserCreate, UserUpdate, UserLogin,
    TokenResponse, PasswordResetRequest, PasswordResetConfirm,
    
    # Category schemas
    CategoryBase, CategoryCreate, CategoryUpdate,
    
    # Tag schemas
    TagBase, TagCreate, TagUpdate,
    
    # Article schemas
    ArticleBase, ArticleDetail, ArticleCreate, ArticleUpdate, ArticleListResponse,
    
    # Comment schemas
    CommentBase, CommentCreate, CommentUpdate, CommentListResponse,
    
    # Like schemas
    LikeBase, LikeCreate,
    
    # Bookmark schemas
    BookmarkBase, BookmarkCreate,
    
    # Search schemas
    SearchQuery,
    
    # Error schemas
    ErrorResponse, ValidationErrorResponse,
    
    # Statistics schemas
    StatisticsResponse,
    
    # Health check schemas
    HealthCheckResponse,
)

from .services import (
    AuthService, ArticleService, CommentService,
    CategoryService, TagService, LikeService,
    BookmarkService, SearchService, StatisticsService
)

from .permissions import (
    IsAuthenticated, IsAdminUser, IsEditorUser,
    IsAuthorUser, IsOwnerOrAdmin, IsOwnerOrReadOnly,
    CanPublishArticles, CanModerateComments
)

from .logging_config import logger, log_operation


# Создаем API
api = NinjaAPI(
    title="Blog API",
    version="1.0.0",
    description="Full-featured blog API with JWT authentication",
    docs_url="/docs",
    openapi_url="/openapi.json",
    auth=None,  # Устанавливаем глобально в роутерах
)

# Создаем роутеры
auth_router = Router(tags=["Authentication"])
users_router = Router(tags=["Users"])
categories_router = Router(tags=["Categories"])
tags_router = Router(tags=["Tags"])
articles_router = Router(tags=["Articles"])
comments_router = Router(tags=["Comments"])
likes_router = Router(tags=["Likes"])
bookmarks_router = Router(tags=["Bookmarks"])
search_router = Router(tags=["Search"])
stats_router = Router(tags=["Statistics"])
health_router = Router(tags=["Health"])


# Health check endpoints
@health_router.get("/", response=HealthCheckResponse)
def health_check(request: HttpRequest):
    """
    Health check endpoint
    """
    from django.db import connection
    from redis import Redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    
    status = {
        "status": "healthy",
        "timestamp": timezone.now(),
        "database": False,
        "redis": False,
        "celery": False,
    }
    
    # Проверяем базу данных
    try:
        connection.ensure_connection()
        status["database"] = True
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
    
    # Проверяем Redis
    try:
        redis_client = Redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        status["redis"] = True
    except RedisConnectionError as e:
        logger.error("redis_health_check_failed", error=str(e))
    
    # Проверяем Celery
    # (Упрощенная проверка - проверяем подключение к брокеру)
    status["celery"] = status["redis"]  # Если Redis работает, Celery тоже должен
    
    return status


# Authentication endpoints
@auth_router.post("/register", response={201: TokenResponse, 400: ErrorResponse})
@log_operation("user_registration")
def register(request: HttpRequest, data: UserCreate):
    """
    Регистрация нового пользователя
    """
    try:
        # Проверяем существующего пользователя
        if User.objects.filter(email=data.email).exists():
            return 400, {
                "detail": "User with this email already exists",
                "code": "email_exists"
            }
        
        if User.objects.filter(username=data.username).exists():
            return 400, {
                "detail": "User with this username already exists",
                "code": "username_exists"
            }
        
        # Создаем пользователя
        user = AuthService.register_user(
            username=data.username,
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name
        )
        
        # Генерируем JWT токены
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Формируем ответ
        response_data = {
            "access": access_token,
            "refresh": str(refresh),
            "access_expires": timezone.now() + refresh.access_token.lifetime,
            "refresh_expires": timezone.now() + refresh.lifetime,
            "user": UserBase.from_orm(user)
        }
        
        logger.info(
            "user_registered_successfully",
            user_id=user.id,
            username=user.username,
            email=user.email
        )
        
        return 201, response_data
        
    except Exception as e:
        logger.error(
            "user_registration_failed",
            error=str(e),
            email=data.email,
            username=data.username
        )
        
        return 400, {
            "detail": str(e),
            "code": "registration_failed"
        }


@auth_router.post("/login", response={200: TokenResponse, 400: ErrorResponse})
@log_operation("user_login")
def login(request: HttpRequest, data: UserLogin):
    """
    Аутентификация пользователя
    """
    try:
        # Пытаемся найти пользователя по email
        user = User.objects.filter(email=data.email).first()
        
        if not user:
            # Ищем по username
            user = User.objects.filter(username=data.email).first()
        
        if not user:
            logger.warning("login_failed_user_not_found", email=data.email)
            return 400, {
                "detail": "Invalid credentials",
                "code": "invalid_credentials"
            }
        
        # Проверяем пароль
        if not user.check_password(data.password):
            logger.warning("login_failed_invalid_password", user_id=user.id)
            return 400, {
                "detail": "Invalid credentials",
                "code": "invalid_credentials"
            }
        
        # Проверяем активность пользователя
        if not user.is_active:
            logger.warning("login_failed_user_inactive", user_id=user.id)
            return 400, {
                "detail": "User account is inactive",
                "code": "account_inactive"
            }
        
        # Обновляем статистику логинов
        user.increment_login_count(request.META.get('REMOTE_ADDR'))
        
        # Генерируем JWT токены
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Формируем ответ
        response_data = {
            "access": access_token,
            "refresh": str(refresh),
            "access_expires": timezone.now() + refresh.access_token.lifetime,
            "refresh_expires": timezone.now() + refresh.lifetime,
            "user": UserBase.from_orm(user)
        }
        
        logger.info(
            "user_logged_in_successfully",
            user_id=user.id,
            username=user.username
        )
        
        return 200, response_data
        
    except Exception as e:
        logger.error(
            "login_failed",
            error=str(e),
            email=data.email
        )
        
        return 400, {
            "detail": "Authentication failed",
            "code": "authentication_failed"
        }


@auth_router.post("/refresh", response={200: TokenResponse, 400: ErrorResponse})
@log_operation("token_refresh")
def refresh_token(request: HttpRequest, refresh: str):
    """
    Обновление access токена
    """
    try:
        refresh_token = RefreshToken(refresh)
        user = refresh_token.get_user()
        
        if not user.is_active:
            return 400, {
                "detail": "User account is inactive",
                "code": "account_inactive"
            }
        
        # Генерируем новый access токен
        new_refresh = RefreshToken.for_user(user)
        access_token = str(new_refresh.access_token)
        
        response_data = {
            "access": access_token,
            "refresh": str(new_refresh),
            "access_expires": timezone.now() + new_refresh.access_token.lifetime,
            "refresh_expires": timezone.now() + new_refresh.lifetime,
            "user": UserBase.from_orm(user)
        }
        
        logger.info("token_refreshed", user_id=user.id)
        
        return 200, response_data
        
    except Exception as e:
        logger.error("token_refresh_failed", error=str(e))
        return 400, {
            "detail": "Invalid refresh token",
            "code": "invalid_refresh_token"
        }


@auth_router.post("/logout", response={200: Dict[str, str], 400: ErrorResponse})
@log_operation("user_logout")
def logout(request: HttpRequest, refresh: str):
    """
    Выход пользователя (инвалидация refresh токена)
    """
    try:
        refresh_token = RefreshToken(refresh)
        refresh_token.blacklist()
        
        logger.info("user_logged_out", user_id=refresh_token.get_user().id)
        
        return 200, {"detail": "Successfully logged out"}
        
    except Exception as e:
        logger.error("logout_failed", error=str(e))
        return 400, {
            "detail": "Invalid refresh token",
            "code": "invalid_refresh_token"
        }


# User endpoints
@users_router.get("/me", response=UserBase, auth=JWTAuth())
@log_operation("get_current_user")
def get_current_user(request: HttpRequest):
    """
    Получение информации о текущем пользователе
    """
    return request.user


@users_router.put("/me", response=UserBase, auth=JWTAuth())
@log_operation("update_current_user")
def update_current_user(request: HttpRequest, data: UserUpdate):
    """
    Обновление информации о текущем пользователе
    """
    user = request.user
    
    try:
        # Обновляем поля пользователя
        for field, value in data.dict(exclude_unset=True).items():
            if value is not None:
                setattr(user, field, value)
        
        user.save()
        
        logger.info("user_updated", user_id=user.id)
        
        return user
        
    except Exception as e:
        logger.error("user_update_failed", user_id=user.id, error=str(e))
        
        return 400, {
            "detail": str(e),
            "code": "update_failed"
        }


@users_router.post("/me/change-password", response={200: Dict[str, str], 400: ErrorResponse}, auth=JWTAuth())
@log_operation("change_password")
def change_password(
    request: HttpRequest,
    current_password: str,
    new_password: str,
    confirm_password: str
):
    """
    Смена пароля текущего пользователя
    """
    user = request.user
    
    try:
        # Проверяем текущий пароль
        if not user.check_password(current_password):
            return 400, {
                "detail": "Current password is incorrect",
                "code": "incorrect_password"
            }
        
        # Проверяем совпадение новых паролей
        if new_password != confirm_password:
            return 400, {
                "detail": "New passwords do not match",
                "code": "passwords_mismatch"
            }
        
        # Проверяем сложность пароля
        if len(new_password) < 8:
            return 400, {
                "detail": "Password must be at least 8 characters long",
                "code": "weak_password"
            }
        
        # Устанавливаем новый пароль
        user.set_password(new_password)
        user.save()
        
        logger.info("password_changed", user_id=user.id)
        
        return 200, {"detail": "Password changed successfully"}
        
    except Exception as e:
        logger.error("password_change_failed", user_id=user.id, error=str(e))
        
        return 400, {
            "detail": str(e),
            "code": "password_change_failed"
        }


@users_router.get("/{user_id}", response=UserBase)
@log_operation("get_user")
def get_user(request: HttpRequest, user_id: int):
    """
    Получение информации о пользователе по ID
    """
    user = get_object_or_404(User, id=user_id, is_active=True)
    
    # Проверяем видимость профиля
    if not user.profile.public_profile and request.user != user:
        return 403, {
            "detail": "You don't have permission to view this profile",
            "code": "permission_denied"
        }
    
    return user


# Category endpoints
@categories_router.get("/", response=List[CategoryBase])
@log_operation("list_categories")
def list_categories(
    request: HttpRequest,
    parent_id: Optional[int] = None,
    is_active: bool = True
):
    """
    Получение списка категорий
    """
    queryset = Category.objects.filter(is_active=is_active)
    
    if parent_id:
        queryset = queryset.filter(parent_id=parent_id)
    else:
        queryset = queryset.filter(parent__isnull=True)
    
    queryset = queryset.order_by('sort_order', 'name')
    
    logger.info(
        "categories_listed",
        count=queryset.count(),
        parent_id=parent_id,
        is_active=is_active
    )
    
    return list(queryset)


@categories_router.get("/{category_id_or_slug}", response=CategoryBase)
@log_operation("get_category")
def get_category(request: HttpRequest, category_id_or_slug: str):
    """
    Получение информации о категории по ID или slug
    """
    try:
        if category_id_or_slug.isdigit():
            category = get_object_or_404(
                Category.objects.select_related('parent'),
                id=int(category_id_or_slug)
            )
        else:
            category = get_object_or_404(
                Category.objects.select_related('parent'),
                slug=category_id_or_slug
            )
    except Category.DoesNotExist:
        return 404, {
            "detail": "Category not found",
            "code": "not_found"
        }
    
    logger.info("category_retrieved", category_id=category.id)
    
    return category


@categories_router.post("/", response={201: CategoryBase, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("create_category")
def create_category(request: HttpRequest, data: CategoryCreate):
    """
    Создание новой категории
    """
    # Проверяем права доступа
    if not request.user.is_editor:
        return 403, {
            "detail": "You don't have permission to create categories",
            "code": "permission_denied"
        }
    
    try:
        category = CategoryService.create_category(
            name=data.name,
            description=data.description,
            parent_id=data.parent_id,
            color=data.color,
            icon=data.icon,
            is_active=data.is_active,
            show_in_menu=data.show_in_menu,
            sort_order=data.sort_order,
            meta_title=data.meta_title,
            meta_description=data.meta_description,
            created_by=request.user
        )
        
        logger.info("category_created", category_id=category.id, name=category.name)
        
        return 201, category
        
    except Exception as e:
        logger.error("category_creation_failed", error=str(e))
        
        return 400, {
            "detail": str(e),
            "code": "creation_failed"
        }


@categories_router.put("/{category_id}", response={200: CategoryBase, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("update_category")
def update_category(request: HttpRequest, category_id: int, data: CategoryUpdate):
    """
    Обновление категории
    """
    category = get_object_or_404(Category, id=category_id)
    
    # Проверяем права доступа
    if not request.user.is_editor:
        return 403, {
            "detail": "You don't have permission to update categories",
            "code": "permission_denied"
        }
    
    try:
        updated_category = CategoryService.update_category(
            category=category,
            **data.dict(exclude_unset=True)
        )
        
        logger.info("category_updated", category_id=category.id)
        
        return updated_category
        
    except Exception as e:
        logger.error("category_update_failed", category_id=category.id, error=str(e))
        
        return 400, {
            "detail": str(e),
            "code": "update_failed"
        }


@categories_router.delete("/{category_id}", response={204: None, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("delete_category")
def delete_category(request: HttpRequest, category_id: int):
    """
    Удаление категории
    """
    category = get_object_or_404(Category, id=category_id)
    
    # Проверяем права доступа
    if not request.user.is_admin:
        return 403, {
            "detail": "You don't have permission to delete categories",
            "code": "permission_denied"
        }
    
    try:
        CategoryService.delete_category(category)
        
        logger.info("category_deleted", category_id=category.id)
        
        return 204, None
        
    except Exception as e:
        logger.error("category_deletion_failed", category_id=category.id, error=str(e))
        
        return 400, {
            "detail": str(e),
            "code": "deletion_failed"
        }


# Tag endpoints
@tags_router.get("/", response=List[TagBase])
@log_operation("list_tags")
def list_tags(request: HttpRequest):
    """
    Получение списка тегов
    """
    tags = Tag.objects.all().order_by('name')
    
    logger.info("tags_listed", count=tags.count())
    
    return list(tags)


@tags_router.get("/popular", response=List[TagBase])
@log_operation("list_popular_tags")
def list_popular_tags(request: HttpRequest, limit: int = 20):
    """
    Получение списка популярных тегов
    """
    tags = Tag.objects.annotate(
        usage_count_total=Count('articles')
    ).order_by('-usage_count_total', 'name')[:limit]
    
    logger.info("popular_tags_listed", count=tags.count())
    
    return list(tags)


@tags_router.post("/", response={201: TagBase, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("create_tag")
def create_tag(request: HttpRequest, data: TagCreate):
    """
    Создание нового тега
    """
    # Проверяем права доступа
    if not request.user.is_editor:
        return 403, {
            "detail": "You don't have permission to create tags",
            "code": "permission_denied"
        }
    
    try:
        tag = TagService.create_tag(
            name=data.name,
            description=data.description,
            created_by=request.user
        )
        
        logger.info("tag_created", tag_id=tag.id, name=tag.name)
        
        return 201, tag
        
    except Exception as e:
        logger.error("tag_creation_failed", error=str(e))
        
        return 400, {
            "detail": str(e),
            "code": "creation_failed"
        }


# Article endpoints
@articles_router.get("/", response=ArticleListResponse)
@paginate(PageNumberPagination, page_size=10)
@log_operation("list_articles")
def list_articles(
    request: HttpRequest,
    status: Optional[str] = "published",
    category: Optional[str] = None,
    tag: Optional[str] = None,
    author: Optional[str] = None,
    is_featured: Optional[bool] = None,
    is_pinned: Optional[bool] = None,
    article_type: Optional[str] = None,
    ordering: Optional[str] = "-published_at"
):
    """
    Получение списка статей с фильтрацией и пагинацией
    """
    queryset = Article.objects.select_related(
        'author', 'category'
    ).prefetch_related('tags')
    
    # Фильтрация по статусу
    if status:
        queryset = queryset.filter(status=status)
    
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
    
    # Фильтрация по флагам
    if is_featured is not None:
        queryset = queryset.filter(is_featured=is_featured)
    
    if is_pinned is not None:
        queryset = queryset.filter(is_pinned=is_pinned)
    
    if article_type:
        queryset = queryset.filter(article_type=article_type)
    
    # Сортировка
    if ordering:
        queryset = queryset.order_by(ordering)
    
    logger.info(
        "articles_listed",
        count=queryset.count(),
        filters={
            "status": status,
            "category": category,
            "tag": tag,
            "author": author,
            "is_featured": is_featured,
            "is_pinned": is_pinned,
            "article_type": article_type,
            "ordering": ordering
        }
    )
    
    return queryset


@articles_router.get("/featured", response=List[ArticleBase])
@log_operation("list_featured_articles")
def list_featured_articles(request: HttpRequest, limit: int = 5):
    """
    Получение списка рекомендуемых статей
    """
    cache_key = f"featured_articles_{limit}"
    cached = cache.get(cache_key)
    
    if cached is not None:
        logger.debug("featured_articles_cache_hit", cache_key=cache_key)
        return cached
    
    articles = ArticleService.get_featured_articles(limit)
    
    # Кэшируем на 1 час
    cache.set(cache_key, articles, 3600)
    
    logger.info("featured_articles_listed", count=len(articles))
    
    return articles


@articles_router.get("/popular", response=List[ArticleBase])
@log_operation("list_popular_articles")
def list_popular_articles(request: HttpRequest, limit: int = 10):
    """
    Получение списка популярных статей
    """
    cache_key = f"popular_articles_{limit}"
    cached = cache.get(cache_key)
    
    if cached is not None:
        logger.debug("popular_articles_cache_hit", cache_key=cache_key)
        return cached
    
    articles = ArticleService.get_popular_articles(limit)
    
    # Кэшируем на 30 минут
    cache.set(cache_key, articles, 1800)
    
    logger.info("popular_articles_listed", count=len(articles))
    
    return articles


@articles_router.get("/{article_id_or_slug}", response=ArticleDetail)
@log_operation("get_article")
def get_article(request: HttpRequest, article_id_or_slug: str):
    """
    Получение информации о статье по ID или slug
    """
    try:
        if article_id_or_slug.isdigit():
            article = get_object_or_404(
                Article.objects.select_related('author', 'category', 'last_edited_by')
                .prefetch_related('tags'),
                id=int(article_id_or_slug)
            )
        else:
            article = get_object_or_404(
                Article.objects.select_related('author', 'category', 'last_edited_by')
                .prefetch_related('tags'),
                slug=article_id_or_slug
            )
    except Article.DoesNotExist:
        return 404, {
            "detail": "Article not found",
            "code": "not_found"
        }
    
    # Проверяем доступ
    if not article.is_published and not request.user.is_authenticated:
        return 403, {
            "detail": "This article is not published",
            "code": "not_published"
        }
    
    if article.require_login and not request.user.is_authenticated:
        return 401, {
            "detail": "Login required to view this article",
            "code": "login_required"
        }
    
    # Увеличиваем счетчик просмотров
    ArticleService.increment_view_count(article, request)
    
    logger.info(
        "article_retrieved",
        article_id=article.id,
        title=article.title,
        view_count=article.view_count
    )
    
    return article


@articles_router.post("/", response={201: ArticleDetail, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("create_article")
def create_article(request: HttpRequest, data: ArticleCreate):
    """
    Создание новой статьи
    """
    # Проверяем права доступа
    if not request.user.is_author:
        return 403, {
            "detail": "You don't have permission to create articles",
            "code": "permission_denied"
        }
    
    try:
        article = ArticleService.create_article(
            author=request.user,
            title=data.title,
            content=data.content,
            excerpt=data.excerpt,
            category_id=data.category_id,
            tag_ids=data.tag_ids,
            status=data.status,
            article_type=data.article_type,
            featured_image=data.featured_image,
            image_caption=data.image_caption,
            meta_title=data.meta_title,
            meta_description=data.meta_description,
            canonical_url=data.canonical_url,
            is_featured=data.is_featured,
            is_pinned=data.is_pinned,
            allow_comments=data.allow_comments,
            allow_sharing=data.allow_sharing,
            require_login=data.require_login,
            scheduled_at=data.scheduled_at
        )
        
        logger.info(
            "article_created",
            article_id=article.id,
            title=article.title,
            author_id=request.user.id
        )
        
        return 201, article
        
    except Exception as e:
        logger.error(
            "article_creation_failed",
            author_id=request.user.id,
            error=str(e)
        )
        
        return 400, {
            "detail": str(e),
            "code": "creation_failed"
        }


@articles_router.put("/{article_id}", response={200: ArticleDetail, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("update_article")
def update_article(request: HttpRequest, article_id: int, data: ArticleUpdate):
    """
    Обновление статьи
    """
    article = get_object_or_404(Article, id=article_id)
    
    # Проверяем права доступа
    if not article.can_edit(request.user):
        return 403, {
            "detail": "You don't have permission to edit this article",
            "code": "permission_denied"
        }
    
    try:
        updated_article = ArticleService.update_article(
            article=article,
            editor=request.user,
            **data.dict(exclude_unset=True)
        )
        
        logger.info(
            "article_updated",
            article_id=article.id,
            editor_id=request.user.id
        )
        
        return updated_article
        
    except Exception as e:
        logger.error(
            "article_update_failed",
            article_id=article.id,
            editor_id=request.user.id,
            error=str(e)
        )
        
        return 400, {
            "detail": str(e),
            "code": "update_failed"
        }


@articles_router.delete("/{article_id}", response={204: None, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("delete_article")
def delete_article(request: HttpRequest, article_id: int):
    """
    Удаление статьи
    """
    article = get_object_or_404(Article, id=article_id)
    
    # Проверяем права доступа
    if not article.can_delete(request.user):
        return 403, {
            "detail": "You don't have permission to delete this article",
            "code": "permission_denied"
        }
    
    try:
        ArticleService.delete_article(article)
        
        logger.info(
            "article_deleted",
            article_id=article.id,
            deleter_id=request.user.id
        )
        
        return 204, None
        
    except Exception as e:
        logger.error(
            "article_deletion_failed",
            article_id=article.id,
            error=str(e)
        )
        
        return 400, {
            "detail": str(e),
            "code": "deletion_failed"
        }


@articles_router.post("/{article_id}/like", response={200: Dict[str, str], 400: ErrorResponse}, auth=JWTAuth())
@log_operation("like_article")
def like_article(request: HttpRequest, article_id: int):
    """
    Лайк статьи
    """
    article = get_object_or_404(Article, id=article_id)
    
    if not article.is_published:
        return 400, {
            "detail": "Cannot like unpublished article",
            "code": "not_published"
        }
    
    try:
        action = LikeService.toggle_like(
            user=request.user,
            article=article,
            like_type='like'
        )
        
        logger.info(
            "article_liked",
            article_id=article.id,
            user_id=request.user.id,
            action=action
        )
        
        if action == 'added':
            return 200, {"detail": "Article liked successfully"}
        else:
            return 200, {"detail": "Article like removed"}
        
    except Exception as e:
        logger.error(
            "article_like_failed",
            article_id=article.id,
            user_id=request.user.id,
            error=str(e)
        )
        
        return 400, {
            "detail": str(e),
            "code": "like_failed"
        }


# Comment endpoints
@comments_router.get("/article/{article_id}", response=CommentListResponse)
@paginate(PageNumberPagination, page_size=20)
@log_operation("list_comments")
def list_comments(
    request: HttpRequest,
    article_id: int,
    parent_id: Optional[int] = None,
    status: str = "approved"
):
    """
    Получение списка комментариев к статье
    """
    article = get_object_or_404(Article, id=article_id)
    
    if not article.allow_comments:
        return 400, {
            "detail": "Comments are not allowed for this article",
            "code": "comments_disabled"
        }
    
    queryset = Comment.objects.filter(
        article=article,
        status=status
    ).select_related('author')
    
    if parent_id:
        queryset = queryset.filter(parent_id=parent_id)
    else:
        queryset = queryset.filter(parent__isnull=True)
    
    queryset = queryset.order_by('created_at')
    
    logger.info(
        "comments_listed",
        article_id=article.id,
        count=queryset.count(),
        parent_id=parent_id,
        status=status
    )
    
    return queryset


@comments_router.post("/", response={201: CommentBase, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("create_comment")
def create_comment(request: HttpRequest, data: CommentCreate):
    """
    Создание нового комментария
    """
    article = get_object_or_404(Article, id=data.article_id)
    
    if not article.allow_comments:
        return 400, {
            "detail": "Comments are not allowed for this article",
            "code": "comments_disabled"
        }
    
    try:
        comment = CommentService.create_comment(
            author=request.user,
            article=article,
            content=data.content,
            parent_id=data.parent_id,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        
        logger.info(
            "comment_created",
            comment_id=comment.id,
            article_id=article.id,
            author_id=request.user.id
        )
        
        return 201, comment
        
    except Exception as e:
        logger.error(
            "comment_creation_failed",
            article_id=article.id,
            author_id=request.user.id,
            error=str(e)
        )
        
        return 400, {
            "detail": str(e),
            "code": "creation_failed"
        }


@comments_router.put("/{comment_id}", response={200: CommentBase, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("update_comment")
def update_comment(request: HttpRequest, comment_id: int, data: CommentUpdate):
    """
    Обновление комментария
    """
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Проверяем права доступа
    if not comment.can_edit(request.user):
        return 403, {
            "detail": "You don't have permission to edit this comment",
            "code": "permission_denied"
        }
    
    try:
        updated_comment = CommentService.update_comment(
            comment=comment,
            content=data.content,
            edit_reason=data.edit_reason
        )
        
        logger.info(
            "comment_updated",
            comment_id=comment.id,
            editor_id=request.user.id
        )
        
        return updated_comment
        
    except Exception as e:
        logger.error(
            "comment_update_failed",
            comment_id=comment.id,
            editor_id=request.user.id,
            error=str(e)
        )
        
        return 400, {
            "detail": str(e),
            "code": "update_failed"
        }


@comments_router.delete("/{comment_id}", response={204: None, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("delete_comment")
def delete_comment(request: HttpRequest, comment_id: int):
    """
    Удаление комментария
    """
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Проверяем права доступа
    if not comment.can_delete(request.user):
        return 403, {
            "detail": "You don't have permission to delete this comment",
            "code": "permission_denied"
        }
    
    try:
        CommentService.delete_comment(comment)
        
        logger.info(
            "comment_deleted",
            comment_id=comment.id,
            deleter_id=request.user.id
        )
        
        return 204, None
        
    except Exception as e:
        logger.error(
            "comment_deletion_failed",
            comment_id=comment.id,
            error=str(e)
        )
        
        return 400, {
            "detail": str(e),
            "code": "deletion_failed"
        }


@comments_router.post("/{comment_id}/like", response={200: Dict[str, str], 400: ErrorResponse}, auth=JWTAuth())
@log_operation("like_comment")
def like_comment(request: HttpRequest, comment_id: int, like_type: str = "like"):
    """
    Лайк/дизлайк комментария
    """
    comment = get_object_or_404(Comment, id=comment_id)
    
    if not comment.is_approved:
        return 400, {
            "detail": "Cannot like unapproved comment",
            "code": "not_approved"
        }
    
    if like_type not in ['like', 'dislike']:
        return 400, {
            "detail": "Invalid like type. Use 'like' or 'dislike'",
            "code": "invalid_like_type"
        }
    
    try:
        action = LikeService.toggle_like(
            user=request.user,
            comment=comment,
            like_type=like_type
        )
        
        logger.info(
            "comment_liked",
            comment_id=comment.id,
            user_id=request.user.id,
            like_type=like_type,
            action=action
        )
        
        if action == 'added':
            return 200, {"detail": f"Comment {like_type}d successfully"}
        else:
            return 200, {"detail": f"Comment {like_type} removed"}
        
    except Exception as e:
        logger.error(
            "comment_like_failed",
            comment_id=comment.id,
            user_id=request.user.id,
            error=str(e)
        )
        
        return 400, {
            "detail": str(e),
            "code": "like_failed"
        }


# Bookmark endpoints
@bookmarks_router.get("/", response=List[BookmarkBase], auth=JWTAuth())
@log_operation("list_bookmarks")
def list_bookmarks(request: HttpRequest):
    """
    Получение списка закладок пользователя
    """
    bookmarks = BookmarkService.get_user_bookmarks(request.user)
    
    logger.info("bookmarks_listed", user_id=request.user.id, count=bookmarks.count())
    
    return list(bookmarks)


@bookmarks_router.post("/", response={201: BookmarkBase, 400: ErrorResponse}, auth=JWTAuth())
@log_operation("create_bookmark")
def create_bookmark(request: HttpRequest, data: BookmarkCreate):
    """
    Создание закладки
    """
    article = get_object_or_404(Article, id=data.article_id)
    
    if not article.is_published:
        return 400, {
            "detail": "Cannot bookmark unpublished article",
            "code": "not_published"
        }
    
    try:
        bookmark = BookmarkService.toggle_bookmark(
            user=request.user,
            article=article
        )
        
        logger.info(
            "bookmark_toggled",
            article_id=article.id,
            user_id=request.user.id,
            action="created" if bookmark else "removed"
        )
        
        if bookmark:
            return 201, bookmark
        else:
            return 200, {"detail": "Bookmark removed"}
        
    except Exception as e:
        logger.error(
            "bookmark_operation_failed",
            article_id=article.id,
            user_id=request.user.id,
            error=str(e)
        )
        
        return 400, {
            "detail": str(e),
            "code": "bookmark_failed"
        }


# Search endpoints
@search_router.get("/", response=ArticleListResponse)
@paginate(PageNumberPagination, page_size=10)
@log_operation("search_articles")
def search_articles(request: HttpRequest, query: SearchQuery = Query(...)):
    """
    Поиск статей
    """
    try:
        results = SearchService.search_articles(
            query=query.q,
            category=query.category,
            tag=query.tag,
            author=query.author,
            status=query.status,
            date_from=query.date_from,
            date_to=query.date_to,
            ordering=query.ordering
        )
        
        logger.info(
            "articles_searched",
            query=query.q,
            filters={
                "category": query.category,
                "tag": query.tag,
                "author": query.author,
                "status": query.status,
                "date_from": query.date_from,
                "date_to": query.date_to,
                "ordering": query.ordering
            },
            count=results.count()
        )
        
        return results
        
    except Exception as e:
        logger.error("search_failed", query=query.q, error=str(e))
        
        return 400, {
            "detail": str(e),
            "code": "search_failed"
        }


# Statistics endpoints
@stats_router.get("/", response=StatisticsResponse, auth=JWTAuth())
@log_operation("get_statistics")
def get_statistics(request: HttpRequest):
    """
    Получение статистики блога
    """
    # Проверяем права доступа
    if not request.user.is_editor:
        return 403, {
            "detail": "You don't have permission to view statistics",
            "code": "permission_denied"
        }
    
    try:
        statistics = StatisticsService.get_blog_statistics()
        
        logger.info("statistics_retrieved", user_id=request.user.id)
        
        return statistics
        
    except Exception as e:
        logger.error("statistics_retrieval_failed", error=str(e))
        
        return 400, {
            "detail": str(e),
            "code": "statistics_failed"
        }


# Регистрируем роутеры в API
api.add_router("/auth", auth_router)
api.add_router("/users", users_router)
api.add_router("/categories", categories_router)
api.add_router("/tags", tags_router)
api.add_router("/articles", articles_router)
api.add_router("/comments", comments_router, auth=JWTAuth())
api.add_router("/bookmarks", bookmarks_router, auth=JWTAuth())
api.add_router("/search", search_router)
api.add_router("/stats", stats_router, auth=JWTAuth())
api.add_router("/health", health_router)

# Добавляем JWT контроллеры
api.add_router("/token", TokenObtainPairController().router)
api.add_router("/token/refresh", TokenRefreshController().router)


# Обработчик ошибок
@api.exception_handler(Exception)
def handle_exception(request: HttpRequest, exc: Exception):
    """
    Глобальный обработчик исключений
    """
    import traceback
    
    # Логируем ошибку
    logger.error(
        "unhandled_exception",
        error=str(exc),
        traceback=traceback.format_exc(),
        path=request.path,
        method=request.method
    )
    
    # Возвращаем структурированный ответ
    return api.create_response(
        request,
        {
            "detail": "Internal server error",
            "code": "internal_error"
        },
        status=500
    )
