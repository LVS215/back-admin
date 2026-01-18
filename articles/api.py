from ninja import Router, Query
from ninja.pagination import paginate, PageNumberPagination
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404
from typing import List, Optional
import structlog

from articles.models import Article, Category
from articles.schemas import ArticleIn, ArticleOut, ArticleUpdate, CategoryIn, CategoryOut
from users.models import User

router = Router(tags=["articles"])
logger = structlog.get_logger(__name__)

@router.get("/", response=List[ArticleOut])
@paginate(PageNumberPagination, page_size=10)
def list_articles(
    request,
    category: Optional[str] = None,
    author: Optional[str] = None,
    status: Optional[str] = "published",
    search: Optional[str] = None
):
    """Список статей с фильтрацией"""
    queryset = Article.objects.all()
    
    if category:
        queryset = queryset.filter(category__slug=category)
    
    if author:
        queryset = queryset.filter(author__username=author)
    
    if status:
        queryset = queryset.filter(status=status)
    
    if search:
        queryset = queryset.filter(title__icontains=search)
    
    logger.info("Articles listed", filter={
        "category": category,
        "author": author,
        "status": status,
        "search": search
    })
    
    return queryset

@router.post("/", response=ArticleOut)
def create_article(request, payload: ArticleIn):
    """Создание новой статьи"""
    user = request.auth
    
    category = None
    if payload.category_slug:
        category = get_object_or_404(Category, slug=payload.category_slug)
    
    article = Article.objects.create(
        title=payload.title,
        content=payload.content,
        excerpt=payload.excerpt,
        author=user,
        category=category,
        status=payload.status,
        slug=payload.slug,
    )
    
    logger.info("Article created", article_id=str(article.id), author_id=str(user.id))
    
    return article

@router.get("/{slug}", response=ArticleOut)
def get_article(request, slug: str):
    """Получение статьи по slug"""
    article = get_object_or_404(Article, slug=slug)
    logger.info("Article retrieved", article_id=str(article.id), slug=slug)
    return article

@router.put("/{slug}", response=ArticleOut)
def update_article(request, slug: str, payload: ArticleUpdate):
    """Обновление статьи"""
    article = get_object_or_404(Article, slug=slug)
    user = request.auth
    
    if article.author != user and not user.is_superuser:
        logger.warning("Unauthorized article update attempt", 
                      article_id=str(article.id), user_id=str(user.id))
        raise HttpError(403, "You can only update your own articles")
    
    if payload.title:
        article.title = payload.title
    
    if payload.content:
        article.content = payload.content
    
    if payload.excerpt is not None:
        article.excerpt = payload.excerpt
    
    if payload.category_slug:
        category = get_object_or_404(Category, slug=payload.category_slug)
        article.category = category
    
    if payload.status:
        article.status = payload.status
    
    article.save()
    
    logger.info("Article updated", article_id=str(article.id), user_id=str(user.id))
    
    return article

@router.delete("/{slug}")
def delete_article(request, slug: str):
    """Удаление статьи"""
    article = get_object_or_404(Article, slug=slug)
    user = request.auth
    
    if article.author != user and not user.is_superuser:
        logger.warning("Unauthorized article delete attempt", 
                      article_id=str(article.id), user_id=str(user.id))
        raise HttpError(403, "You can only delete your own articles")
    
    article_id = str(article.id)
    article.delete()
    
    logger.info("Article deleted", article_id=article_id, user_id=str(user.id))
    
    return {"success": True}

# Категории
@router.get("/categories/", response=List[CategoryOut])
def list_categories(request):
    """Список категорий"""
    return Category.objects.all()

@router.post("/categories/", response=CategoryOut)
def create_category(request, payload: CategoryIn):
    """Создание категории (только для админов)"""
    if not request.auth.is_superuser:
        raise HttpError(403, "Only admins can create categories")
    
    category = Category.objects.create(**payload.dict())
    logger.info("Category created", category_id=str(category.id))
    return category