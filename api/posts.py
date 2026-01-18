from ninja import Router, Query
from ninja_jwt.authentication import JWTAuth
from django.shortcuts import get_object_or_404
from django.db.models import Q
import logging

from core.models import Post, Category
from core.permissions import IsOwnerOrReadOnly
from .schemas import (
    PostCreateSchema, 
    PostUpdateSchema, 
    PostOutSchema,
    PaginationParams,
    FilterParams
)
from .dependencies import PaginationParams, FilterParams

router = Router(tags=["Posts"])
logger = logging.getLogger(__name__)

@router.get("/", response=List[PostOutSchema])
def list_posts(
    request, 
    pagination: PaginationParams = Query(...),
    filters: FilterParams = Query(...)
):
    """Получение списка статей с пагинацией и фильтрацией"""
    queryset = Post.objects.filter(status='published').select_related('author', 'category')
    
    # Фильтрация
    if filters.category:
        queryset = queryset.filter(category_id=filters.category)
    if filters.author:
        queryset = queryset.filter(author_id=filters.author)
    if filters.search:
        queryset = queryset.filter(
            Q(title__icontains=filters.search) | 
            Q(content__icontains=filters.search)
        )
    
    # Пагинация
    total = queryset.count()
    posts = queryset[pagination.offset:pagination.offset + pagination.limit]
    
    logger.info(f"Posts listed. Total: {total}, Page: {pagination.page}")
    return posts

@router.get("/{post_id}", response=PostOutSchema)
def get_post(request, post_id: int):
    """Получение конкретной статьи"""
    post = get_object_or_404(
        Post.objects.select_related('author', 'category'), 
        id=post_id, 
        status='published'
    )
    
    # Увеличиваем счетчик просмотров
    post.view_count += 1
    post.save(update_fields=['view_count'])
    
    logger.info(f"Post viewed: {post.id} - {post.title}")
    logger.info(f"View count: {post.view_count}")
    return post

@router.post("/", response=PostOutSchema, auth=JWTAuth())
def create_post(request, data: PostCreateSchema):
    """Создание новой статьи (только авторизованные)"""
    category = None
    if data.category_id:
        category = get_object_or_404(Category, id=data.category_id)
    
    post = Post.objects.create(
        title=data.title,
        content=data.content,
        excerpt=data.excerpt or "",
        author=request.user,
        category=category,
        status=data.status
    )
    
    logger.info(f"Post created: {post.id} - {post.title}")
    logger.info(f"Created by user: {request.user.username}")
    return post

@router.put("/{post_id}", response=PostOutSchema, auth=JWTAuth())
def update_post(request, post_id: int, data: PostUpdateSchema):
    """Обновление статьи (только автор)"""
    post = get_object_or_404(Post, id=post_id, author=request.user)
    
    # Обновляем только переданные поля
    for field, value in data.dict(exclude_unset=True).items():
        if field == 'category_id' and value:
            post.category = get_object_or_404(Category, id=value)
        elif field != 'category_id':
            setattr(post, field, value)
    
    post.save()
    
    logger.info(f"Post updated: {post.id} - {post.title}")
    logger.info(f"Updated by user: {request.user.username}")
    return post

@router.delete("/{post_id}", auth=JWTAuth())
def delete_post(request, post_id: int):
    """Удаление статьи (только автор)"""
    post = get_object_or_404(Post, id=post_id, author=request.user)
    post_id = post.id
    post_title = post.title
    post.delete()
    
    logger.warning(f"Post deleted: {post_id} - {post_title}")
    logger.warning(f"Deleted by user: {request.user.username}")
    return {"message": "Post deleted successfully"}
