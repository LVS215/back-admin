from ninja import Router, Query
from ninja_jwt.authentication import JWTAuth
from django.shortcuts import get_object_or_404
import logging

from core.models import Comment, Post
from .schemas import (
    CommentCreateSchema, 
    CommentUpdateSchema, 
    CommentOutSchema,
    PaginationParams
)

router = Router(tags=["Comments"])
logger = logging.getLogger(__name__)

@router.get("/", response=List[CommentOutSchema])
def list_comments(
    request, 
    post_id: int,
    pagination: PaginationParams = Query(...)
):
    """Получение комментариев к статье"""
    post = get_object_or_404(Post, id=post_id, status='published')
    queryset = Comment.objects.filter(
        post=post, 
        is_approved=True
    ).select_related('author')
    
    total = queryset.count()
    comments = queryset[pagination.offset:pagination.offset + pagination.limit]
    
    logger.info(f"Comments listed for post: {post.id}. Total: {total}")
    return comments

@router.post("/", response=CommentOutSchema, auth=JWTAuth())
def create_comment(request, data: CommentCreateSchema):
    """Создание комментария"""
    post = get_object_or_404(Post, id=data.post_id, status='published')
    
    parent = None
    if data.parent_id:
        parent = get_object_or_404(Comment, id=data.parent_id, post=post)
    
    comment = Comment.objects.create(
        content=data.content,
        author=request.user,
        post=post,
        parent=parent
    )
    
    logger.info(f"Comment created: {comment.id}")
    logger.info(f"Created by user: {request.user.username}")
    logger.info(f"Post: {post.id} - {post.title}")
    return comment

@router.put("/{comment_id}", response=CommentOutSchema, auth=JWTAuth())
def update_comment(request, comment_id: int, data: CommentUpdateSchema):
    """Обновление комментария (только автор)"""
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    comment.content = data.content
    comment.save()
    
    logger.info(f"Comment updated: {comment.id}")
    logger.info(f"Updated by user: {request.user.username}")
    return comment

@router.delete("/{comment_id}", auth=JWTAuth())
def delete_comment(request, comment_id: int):
    """Удаление комментария (только автор)"""
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    comment_id = comment.id
    comment.delete()
    
    logger.warning(f"Comment deleted: {comment_id}")
    logger.warning(f"Deleted by user: {request.user.username}")
    return {"message": "Comment deleted successfully"}
