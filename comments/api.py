from ninja import Router
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404
from typing import List
import structlog

from comments.models import Comment
from comments.schemas import CommentIn, CommentOut, CommentUpdate
from articles.models import Article
from users.models import User

router = Router(tags=["comments"])
logger = structlog.get_logger(__name__)

@router.get("/article/{article_slug}/", response=List[CommentOut])
def list_comments(request, article_slug: str):
    """Список комментариев к статье"""
    article = get_object_or_404(Article, slug=article_slug)
    comments = Comment.objects.filter(article=article, parent=None, is_approved=True)
    
    logger.info("Comments listed", article_slug=article_slug, count=comments.count())
    
    return comments

@router.post("/article/{article_slug}/", response=CommentOut)
def create_comment(request, article_slug: str, payload: CommentIn):
    """Создание комментария"""
    article = get_object_or_404(Article, slug=article_slug)
    user = request.auth
    
    parent = None
    if payload.parent_id:
        parent = get_object_or_404(Comment, id=payload.parent_id, article=article)
    
    comment = Comment.objects.create(
        article=article,
        author=user,
        parent=parent,
        content=payload.content,
    )
    
    logger.info("Comment created", 
                comment_id=str(comment.id), 
                article_slug=article_slug,
                user_id=str(user.id))
    
    return comment

@router.put("/{comment_id}", response=CommentOut)
def update_comment(request, comment_id: str, payload: CommentUpdate):
    """Обновление комментария"""
    comment = get_object_or_404(Comment, id=comment_id)
    user = request.auth
    
    if comment.author != user and not user.is_superuser:
        logger.warning("Unauthorized comment update attempt", 
                      comment_id=comment_id, user_id=str(user.id))
        raise HttpError(403, "You can only update your own comments")
    
    comment.content = payload.content
    comment.save()
    
    logger.info("Comment updated", comment_id=comment_id, user_id=str(user.id))
    
    return comment

@router.delete("/{comment_id}")
def delete_comment(request, comment_id: str):
    """Удаление комментария"""
    comment = get_object_or_404(Comment, id=comment_id)
    user = request.auth
    
    if comment.author != user and not user.is_superuser:
        logger.warning("Unauthorized comment delete attempt", 
                      comment_id=comment_id, user_id=str(user.id))
        raise HttpError(403, "You can only delete your own comments")
    
    comment_id_str = comment_id
    comment.delete()
    
    logger.info("Comment deleted", comment_id=comment_id_str, user_id=str(user.id))
    
    return {"success": True}