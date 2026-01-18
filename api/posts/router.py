"""
CRUD операции для статей
Требование: Пользователь может редактировать/удалять только свои статьи
"""
from typing import List, Optional
from ninja import Router, Query
from django.shortcuts import get_object_or_404
from django.db.models import Q
import logging

from core.authentication import TokenAuthentication
from core.permissions import IsAuthenticated, IsPostOwner
from core.exceptions import BlogAPIException
from core.models import Post, Category
from .schemas import (
    PostCreateIn,
    PostUpdateIn,
    PostOut,
    PostListOut,
    PostFilter,
    PostOrder,
)

router = Router(tags=["Posts"], auth=TokenAuthentication())
logger = logging.getLogger(__name__)

@router.get("", response=List[PostListOut])
def list_posts(
    request,
    filters: PostFilter = Query(...),
    order: PostOrder = Query(PostOrder.NEWEST),
    page: int = 1,
    page_size: int = 20,
):
    """
    Получение списка статей с фильтрацией, сортировкой и пагинацией
    """
    # Базовый queryset - только опубликованные статьи
    queryset = Post.objects.filter(status=Post.STATUS_PUBLISHED)
    
    # Применяем фильтры
    if filters.category_id:
        queryset = queryset.filter(category_id=filters.category_id)
    
    if filters.author_id:
        queryset = queryset.filter(author_id=filters.author_id)
    
    if filters.search:
        queryset = queryset.filter(
            Q(title__icontains=filters.search) |
            Q(content__icontains=filters.search) |
            Q(excerpt__icontains=filters.search)
        )
    
    # Применяем сортировку
    if order == PostOrder.NEWEST:
        queryset = queryset.order_by('-published_at', '-created_at')
    elif order == PostOrder.OLDEST:
        queryset = queryset.order_by('published_at', 'created_at')
    elif order == PostOrder.MOST_VIEWED:
        queryset = queryset.order_by('-view_count')
    elif order == PostOrder.MOST_LIKED:
        queryset = queryset.order_by('-like_count')
    
    # Пагинация
    total_count = queryset.count()
    total_pages = (total_count + page_size - 1) // page_size
    
    start = (page - 1) * page_size
    end = start + page_size
    
    posts = queryset[start:end].select_related('author', 'category')
    
    logger.info(
        f"Posts listed: {len(posts)} posts",
        extra={
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'filters': filters.dict(),
            'order': order.value,
            'user': request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous',
        }
    )
    
    return {
        "posts": posts,
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.get("/{post_id}", response=PostOut)
def get_post(request, post_id: int):
    """
    Получение конкретной статьи
    Увеличивает счетчик просмотров
    """
    post = get_object_or_404(
        Post.objects.select_related('author', 'category'),
        id=post_id
    )
    
    # Проверяем доступ (неопубликованные статьи видны только автору)
    if post.status != Post.STATUS_PUBLISHED:
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            raise BlogAPIException(
                detail="Post not found",
                code="post_not_found",
                status_code=404,
            )
        
        if post.author != request.user and not request.user.is_staff:
            raise BlogAPIException(
                detail="Post not found",
                code="post_not_found",
                status_code=404,
            )
    
    # Увеличиваем счетчик просмотров
    post.view_count += 1
    post.save(update_fields=['view_count'])
    
    logger.info(
        f"Post viewed: {post.title} (ID: {post.id})",
        extra={
            'post_id': post.id,
            'post_title': post.title,
            'author': post.author.username,
            'view_count': post.view_count,
            'user': request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous',
        }
    )
    
    return post


@router.post("", response=PostOut, auth=IsAuthenticated())
def create_post(request, data: PostCreateIn):
    """
    Создание новой статьи
    Только для аутентифицированных пользователей
    """
    # Валидация данных
    if len(data.title) < 3:
        raise BlogAPIException(
            detail="Title must be at least 3 characters long",
            code="title_too_short",
            status_code=400,
        )
    
    if len(data.content) < 10:
        raise BlogAPIException(
            detail="Content must be at least 10 characters long",
            code="content_too_short",
            status_code=400,
        )
    
    # Проверяем категорию, если указана
    category = None
    if data.category_id:
        try:
            category = Category.objects.get(id=data.category_id)
        except Category.DoesNotExist:
            raise BlogAPIException(
                detail="Category not found",
                code="category_not_found",
                status_code=404,
            )
    
    # Создаем статью
    post = Post.objects.create(
        title=data.title,
        slug=data.slug or self._generate_slug(data.title),
        content=data.content,
        excerpt=data.excerpt or data.content[:200] + "...",
        author=request.user,
        category=category,
        status=data.status,
        created_by=request.user,
        updated_by=request.user,
    )
    
    logger.info(
        f"Post created: {post.title} (ID: {post.id})",
        extra={
            'post_id': post.id,
            'post_title': post.title,
            'author_id': request.user.id,
            'author_username': request.user.username,
            'status': post.status,
            'category_id': category.id if category else None,
        }
    )
    
    return post


@router.put("/{post_id}", response=PostOut, auth=IsPostOwner())
def update_post(request, post_id: int, data: PostUpdateIn):
    """
    Обновление статьи
    Только автор статьи или администратор
    """
    post = get_object_or_404(Post, id=post_id)
    
    # Обновляем поля, которые были переданы
    update_fields = []
    
    if data.title is not None:
        if len(data.title) < 3:
            raise BlogAPIException(
                detail="Title must be at least 3 characters long",
                code="title_too_short",
                status_code=400,
            )
        post.title = data.title
        update_fields.append('title')
    
    if data.content is not None:
        if len(data.content) < 10:
            raise BlogAPIException(
                detail="Content must be at least 10 characters long",
                code="content_too_short",
                status_code=400,
            )
        post.content = data.content
        update_fields.append('content')
    
    if data.excerpt is not None:
        post.excerpt = data.excerpt
        update_fields.append('excerpt')
    
    if data.status is not None:
        post.status = data.status
        update_fields.append('status')
        
        # Если статья публикуется, устанавливаем published_at
        if data.status == Post.STATUS_PUBLISHED and not post.published_at:
            from django.utils import timezone
            post.published_at = timezone.now()
            update_fields.append('published_at')
    
    if data.category_id is not None:
        if data.category_id == 0:  # Удаляем категорию
            post.category = None
        else:
            try:
                category = Category.objects.get(id=data.category_id)
                post.category = category
            except Category.DoesNotExist:
                raise BlogAPIException(
                    detail="Category not found",
                    code="category_not_found",
                    status_code=404,
                )
        update_fields.append('category')
    
    if update_fields:
        post.updated_by = request.user
        update_fields.append('updated_by')
        post.save(update_fields=update_fields)
    
    logger.info(
        f"Post updated: {post.title} (ID: {post.id})",
        extra={
            'post_id': post.id,
            'post_title': post.title,
            'author_id': request.user.id,
            'author_username': request.user.username,
            'updated_fields': update_fields,
        }
    )
    
    return post


@router.delete("/{post_id}", auth=IsPostOwner())
def delete_post(request, post_id: int):
    """
    Удаление статьи
    Только автор статьи или администратор
    """
    post = get_object_or_404(Post, id=post_id)
    post_title = post.title
    post_id_val = post.id
    
    post.delete()
    
    logger.warning(
        f"Post deleted: {post_title} (ID: {post_id_val})",
        extra={
            'post_id': post_id_val,
            'post_title': post_title,
            'author_id': request.user.id,
            'author_username': request.user.username,
        }
    )
    
    return {"message": "Post deleted successfully"}


@router.get("/my", response=List[PostListOut], auth=IsAuthenticated())
def my_posts(request):
    """
    Получение статей текущего пользователя (включая черновики)
    """
    posts = Post.objects.filter(author=request.user).order_by('-created_at')
    
    logger.info(
        f"My posts listed: {posts.count()} posts",
        extra={
            'user_id': request.user.id,
            'username': request.user.username,
        }
    )
    
    return posts


def _generate_slug(self, title: str) -> str:
    """Генерация slug из заголовка"""
    import re
    from django.utils.text import slugify
    
    # Убираем специальные символы, оставляем только буквы, цифры и пробелы
    cleaned = re.sub(r'[^\w\s-]', '', title.lower())
    # Заменяем пробелы на дефисы
    slug = re.sub(r'[-\s]+', '-', cleaned)
    return slugify(slug)
