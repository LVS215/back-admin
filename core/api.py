from ninja import NinjaAPI, Router
from ninja.security import HttpBearer
from django.shortcuts import get_object_or_404
from django.http import HttpRequest
from typing import List

from .models import User, Article, Comment, Category
from .schemas import *
from .services import AuthService, ArticleService, CommentService
from .logging_config import logger

api = NinjaAPI(title="Blog API", version="1.0.0")

class TokenAuth(HttpBearer):
    def authenticate(self, request: HttpRequest, token: str):
        try:
            user = User.objects.get(token=token)
            logger.info("token_authenticated", user_id=user.id)
            return user
        except User.DoesNotExist:
            logger.warning("token_authentication_failed", token=token[:20])
            return None

auth_router = Router()
article_router = Router()
comment_router = Router()

# Регистрация и аутентификация
@auth_router.post("/register", response={200: TokenResponse, 400: ErrorResponse})
def register(request, data: UserCreate):
    try:
        if User.objects.filter(username=data.username).exists():
            return 400, {"detail": "Username already exists"}
        
        user, token = AuthService.register_user(
            username=data.username,
            password=data.password,
            email=data.email
        )
        
        return 200, {
            "token": token,
            "user": UserSchema.from_orm(user)
        }
    except Exception as e:
        return 400, {"detail": str(e)}

@auth_router.post("/login", response={200: TokenResponse, 401: ErrorResponse})
def login(request, data: UserLogin):
    user, token = AuthService.login_user(data.username, data.password)
    if user and token:
        return 200, {
            "token": token,
            "user": UserSchema.from_orm(user)
        }
    return 401, {"detail": "Invalid credentials"}

# CRUD для статей
@article_router.get("/", response=List[ArticleSchema])
def list_articles(request):
    articles = Article.objects.filter(is_published=True).select_related('author', 'category')
    logger.info("articles_listed", count=articles.count())
    return articles

@article_router.get("/{article_id}", response=ArticleSchema)
def get_article(request, article_id: int):
    article = get_object_or_404(Article, id=article_id, is_published=True)
    logger.info("article_retrieved", article_id=article_id)
    return article

@article_router.post("/", response={200: ArticleSchema, 400: ErrorResponse})
def create_article(request, data: ArticleCreate):
    try:
        article = ArticleService.create_article(request.auth, data.dict())
        return 200, article
    except Exception as e:
        return 400, {"detail": str(e)}

@article_router.put("/{article_id}", response={200: ArticleSchema, 400: ErrorResponse, 403: ErrorResponse})
def update_article(request, article_id: int, data: ArticleUpdate):
    try:
        article = ArticleService.update_article(request.auth, article_id, data.dict(exclude_unset=True))
        return 200, article
    except Article.DoesNotExist:
        return 403, {"detail": "You can only edit your own articles"}
    except Exception as e:
        return 400, {"detail": str(e)}

@article_router.delete("/{article_id}", response={200: dict, 403: ErrorResponse})
def delete_article(request, article_id: int):
    try:
        ArticleService.delete_article(request.auth, article_id)
        return 200, {"detail": "Article deleted successfully"}
    except Article.DoesNotExist:
        return 403, {"detail": "You can only delete your own articles"}

# CRUD для комментариев
@comment_router.get("/article/{article_id}", response=List[CommentSchema])
def list_comments(request, article_id: int):
    comments = Comment.objects.filter(article_id=article_id).select_related('author')
    logger.info("comments_listed", article_id=article_id, count=comments.count())
    return comments

@comment_router.post("/", response={200: CommentSchema, 400: ErrorResponse})
def create_comment(request, data: CommentCreate):
    try:
        comment = CommentService.create_comment(request.auth, data.dict())
        return 200, comment
    except Exception as e:
        return 400, {"detail": str(e)}

@comment_router.put("/{comment_id}", response={200: CommentSchema, 400: ErrorResponse, 403: ErrorResponse})
def update_comment(request, comment_id: int, data: CommentUpdate):
    try:
        comment = CommentService.update_comment(request.auth, comment_id, data.dict())
        return 200, comment
    except Comment.DoesNotExist:
        return 403, {"detail": "You can only edit your own comments"}
    except Exception as e:
        return 400, {"detail": str(e)}

@comment_router.delete("/{comment_id}", response={200: dict, 403: ErrorResponse})
def delete_comment(request, comment_id: int):
    try:
        CommentService.delete_comment(request.auth, comment_id)
        return 200, {"detail": "Comment deleted successfully"}
    except Comment.DoesNotExist:
        return 403, {"detail": "You can only delete your own comments"}

# Регистрация роутеров
api.add_router("/auth", auth_router, tags=["Authentication"])
api.add_router("/articles", article_router, auth=TokenAuth(), tags=["Articles"])
api.add_router("/comments", comment_router, auth=TokenAuth(), tags=["Comments"])
