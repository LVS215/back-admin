"""
CRUD операции для комментариев
Требование: Пользователь может редактировать/удалять только свои комментарии
"""
from typing import List
from ninja import Router, Query
from django.shortcuts import get_object_or_404
import logging

from core.authentication import TokenAuthentication
from core.permissions import IsAuthenticated, IsCommentOwner
from core.exceptions import BlogAPIException
from core.models import Comment, Post
from .schemas import (
    CommentCreateIn,
    CommentUpdateIn,
    CommentOut,
    CommentListOut,
)

router = Router(tags=["Comments"], auth=TokenAuthentication())
logger = logging.getLogger(__name__)

@router.get("", response=List[CommentListOut])
def list_comments(
    request,
    post_id: int,
    page: int = 1,
    page_size: int = 50,
):
    """
    Получение комментариев к статье
    Только одобренные комментарии для неавторизованных пользователей
    """
    # Проверяем существование статьи
    post = get_object_or_404(Post, id=post_id)
    
    # Базовый queryset
    queryset = Comment.objects.filter(post=post)
    
    # Неавторизованные пользователи видят только одобренные комментарии
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        queryset = queryset.filter(is_approved=True)
    # Авторы видят все свои комментарии + одобренные других
    elif not request.user.is_staff:
        queryset = queryset.filter(
            Q(is_approved=True) | Q(author=request.user)
        )
    
    # Сортируем по дате создания
    queryset = queryset.order_by('created_at')
    
    # Пагинация
    total_count = queryset.count()
    total_pages = (total_count + page_size - 1) // page_size
    
    start = (page - 1) * page_size
    end = start + page_size
    
    comments = queryset[start:end].select_related('author', 'post')
    
    logger.info(
        f"Comments listed for post {post_id}: {len(comments)} comments",
        extra={
            'post_id': post_id,
            'post_title': post.title,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'user': request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous',
        }
    )
    
    return {
        "comments": comments,
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.post("", response=CommentOut, auth=IsAuthenticated())
def create_comment(request, data: CommentCreateIn):
    """
    Создание комментария
    Только для аутентифицированных пользователей
    """
    # Проверяем существование статьи
    post = get_object_or_404(Post, id=data.post_id)
    
    # Проверяем, опубликована ли статья
    if post.status != Post.STATUS_PUBLISHED:
        raise BlogAPIException(
            detail="Cannot comment on unpublished post",
            code="post_not_published",
            status_code=400,
        )
    
    # Проверяем родительский комментарий, если указан
    parent = None
    if data.parent_id:
        try:
            parent = Comment.objects.get(id=data.parent_id, post=post)
        except Comment.DoesNotExist:
            raise BlogAPIException(
                detail="Parent comment not found",
                code="parent_comment_not_found",
                status_code=404,
            )
    
    # Валидация содержания комментария
    if len(data.content.strip()) < 1:
        raise BlogAPIException(
            detail="Comment content cannot be empty",
            code="comment_empty",
            status_code=400,
        )
    
    if len(data.content) > 1000:
        raise BlogAPIException(
            detail="Comment is too long (max 1000 characters)",
            code="comment_too_long",
            status_code=400,
        )
    
    # Создаем комментарий
    comment = Comment.objects.create(
        content=data.content.strip(),
        author=request.user,
        post=post,
        parent=parent,
        created_by=request.user,
        updated_by=request.user,
    )
    
    logger.info(
        f"Comment created: ID {comment.id} for post {post.id}",
        extra={
            'comment_id': comment.id,
            'post_id': post.id,
            'post_title': post.title,
            'author_id': request.user.id,
            'author_username': request.user.username,
            'parent_id': parent.id if parent else None,
        }
    )
    
    return comment


@router.put("/{comment_id}", response=CommentOut, auth=IsCommentOwner())
def update_comment(request, comment_id: int, data: CommentUpdateIn):
    """
    Обновление комментария
    Только автор комментария
    """
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Валидация содержания комментария
    if len(data.content.strip()) < 1:
        raise BlogAPIException(
            detail="Comment content cannot be empty",
            code="comment_empty",
            status_code=400,
        )
    
    if len(data.content) > 1000:
        raise BlogAPIException(
            detail="Comment is too long (max 1000 characters)",
            code="comment_too_long",
            status_code=400,
        )
    
    # Обновляем комментарий
    comment.content = data.content.strip()
    comment.updated_by = request.user
    comment.save(update_fields=['content', 'updated_by'])
    
    logger.info(
        f"Comment updated: ID {comment.id}",
        extra={
            'comment_id': comment.id,
            'post_id': comment.post.id,
            'author_id': request.user.id,
            'author_username': request.user.username,
        }
    )
    
    return comment


@router.delete("/{comment_id}", auth=IsCommentOwner())
def delete_comment(request, comment_id: int):
    """
    Удаление комментария
    Только автор комментария или администратор
    """
    comment = get_object_or_404(Comment, id=comment_id)
    comment_id_val = comment.id
    post_id = comment.post.id
    
    comment.delete()
    
    logger.warning(
        f"Comment deleted: ID {comment_id_val}",
        extra={
            'comment_id': comment_id_val,
            'post_id': post_id,
            'author_id': request.user.id,
            'author_username': request.user.username,
        }
    )
    
    return {"message": "Comment deleted successfully"}


@router.get("/my", response=List[CommentListOut], auth=IsAuthenticated())
def my_comments(request):
    """
    Получение комментариев текущего пользователя
    """
    comments = Comment.objects.filter(author=request.user).order_by('-created_at')
    
    logger.info(
        f"My comments listed: {comments.count()} comments",
        extra={
            'user_id': request.user.id,
            'username': request.user.username,
        }
    )
    
    return comments
