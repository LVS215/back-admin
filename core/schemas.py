from ninja import Schema, ModelSchema
from ninja.orm import create_schema
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import Field, validator, EmailStr, HttpUrl, constr
from enum import Enum

from .models import User, Category, Tag, Article, Comment, Like, Bookmark


# Enums для схем
class ArticleStatus(str, Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'
    PENDING = 'pending'
    REJECTED = 'rejected'


class ArticleType(str, Enum):
    ARTICLE = 'article'
    TUTORIAL = 'tutorial'
    NEWS = 'news'
    REVIEW = 'review'
    OTHER = 'other'


class CommentStatus(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    SPAM = 'spam'
    DELETED = 'deleted'


class LikeType(str, Enum):
    LIKE = 'like'
    DISLIKE = 'dislike'


class UserRole(str, Enum):
    ADMIN = 'admin'
    EDITOR = 'editor'
    AUTHOR = 'author'
    USER = 'user'
    GUEST = 'guest'


# Базовые схемы
class BaseSchema(Schema):
    id: int
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(Schema):
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[Any]


# User схемы
class UserBase(BaseSchema):
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool = False
    email_verified: bool = False
    role: UserRole = UserRole.USER
    last_login: Optional[datetime] = None
    last_activity: datetime


class UserCreate(Schema):
    username: constr(min_length=3, max_length=150, regex=r'^[a-zA-Z0-9_.]+$')
    email: EmailStr
    password: constr(min_length=8)
    password_confirm: constr(min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    @validator('password_confirm')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('passwords do not match')
        return v


class UserUpdate(Schema):
    username: Optional[constr(min_length=3, max_length=150, regex=r'^[a-zA-Z0-9_.]+$')] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    birth_date: Optional[datetime] = None
    website: Optional[HttpUrl] = None
    location: Optional[str] = None
    receive_newsletter: Optional[bool] = None
    email_notifications: Optional[bool] = None


class UserLogin(Schema):
    email: EmailStr
    password: str


class TokenResponse(Schema):
    access: str
    refresh: str
    access_expires: datetime
    refresh_expires: datetime
    user: UserBase


class PasswordResetRequest(Schema):
    email: EmailStr


class PasswordResetConfirm(Schema):
    token: str
    password: constr(min_length=8)
    password_confirm: constr(min_length=8)
    
    @validator('password_confirm')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('passwords do not match')
        return v


# Category схемы
class CategoryBase(BaseSchema):
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    parent_name: Optional[str] = None
    full_path: str
    color: str = '#6c757d'
    icon: Optional[str] = None
    is_active: bool = True
    show_in_menu: bool = True
    sort_order: int = 0
    article_count: int = 0


class CategoryCreate(Schema):
    name: constr(min_length=2, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    color: Optional[str] = '#6c757d'
    icon: Optional[str] = None
    is_active: bool = True
    show_in_menu: bool = True
    sort_order: int = 0
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class CategoryUpdate(Schema):
    name: Optional[constr(min_length=2, max_length=100)] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None
    show_in_menu: Optional[bool] = None
    sort_order: Optional[int] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


# Tag схемы
class TagBase(BaseSchema):
    name: str
    slug: str
    description: Optional[str] = None
    usage_count: int = 0


class TagCreate(Schema):
    name: constr(min_length=2, max_length=50)
    description: Optional[str] = None


class TagUpdate(Schema):
    name: Optional[constr(min_length=2, max_length=50)] = None
    description: Optional[str] = None


# Article схемы
class ArticleBase(BaseSchema):
    title: str
    slug: str
    excerpt: Optional[str] = None
    author: UserBase
    category: Optional[CategoryBase] = None
    tags: List[TagBase] = []
    status: ArticleStatus
    article_type: ArticleType
    featured_image: Optional[str] = None
    image_caption: Optional[str] = None
    is_featured: bool = False
    is_pinned: bool = False
    allow_comments: bool = True
    allow_sharing: bool = True
    require_login: bool = False
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    published_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    reading_time: int
    word_count: int


class ArticleDetail(ArticleBase):
    content: str
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical_url: Optional[HttpUrl] = None
    last_edited_by: Optional[UserBase] = None
    last_edited_at: Optional[datetime] = None


class ArticleCreate(Schema):
    title: constr(min_length=5, max_length=200)
    content: constr(min_length=100)
    excerpt: Optional[constr(max_length=500)] = None
    category_id: Optional[int] = None
    tag_ids: Optional[List[int]] = []
    status: ArticleStatus = ArticleStatus.DRAFT
    article_type: ArticleType = ArticleType.ARTICLE
    featured_image: Optional[str] = None
    image_caption: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical_url: Optional[HttpUrl] = None
    is_featured: bool = False
    is_pinned: bool = False
    allow_comments: bool = True
    allow_sharing: bool = True
    require_login: bool = False
    scheduled_at: Optional[datetime] = None


class ArticleUpdate(Schema):
    title: Optional[constr(min_length=5, max_length=200)] = None
    content: Optional[constr(min_length=100)] = None
    excerpt: Optional[constr(max_length=500)] = None
    category_id: Optional[int] = None
    tag_ids: Optional[List[int]] = None
    status: Optional[ArticleStatus] = None
    article_type: Optional[ArticleType] = None
    featured_image: Optional[str] = None
    image_caption: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical_url: Optional[HttpUrl] = None
    is_featured: Optional[bool] = None
    is_pinned: Optional[bool] = None
    allow_comments: Optional[bool] = None
    allow_sharing: Optional[bool] = None
    require_login: Optional[bool] = None
    scheduled_at: Optional[datetime] = None


class ArticleListResponse(PaginatedResponse):
    results: List[ArticleBase]


# Comment схемы
class CommentBase(BaseSchema):
    article_id: int
    article_title: str
    author: UserBase
    parent_id: Optional[int] = None
    content: str
    status: CommentStatus
    is_edited: bool = False
    edited_at: Optional[datetime] = None
    edit_reason: Optional[str] = None
    like_count: int = 0
    dislike_count: int = 0
    replies_count: int = 0
    depth: int = 0


class CommentCreate(Schema):
    article_id: int
    content: constr(min_length=3)
    parent_id: Optional[int] = None


class CommentUpdate(Schema):
    content: constr(min_length=3)
    edit_reason: Optional[str] = None


class CommentListResponse(PaginatedResponse):
    results: List[CommentBase]


# Like схемы
class LikeBase(BaseSchema):
    user: UserBase
    article_id: Optional[int] = None
    article_title: Optional[str] = None
    comment_id: Optional[int] = None
    comment_content: Optional[str] = None
    like_type: LikeType


class LikeCreate(Schema):
    article_id: Optional[int] = None
    comment_id: Optional[int] = None
    like_type: LikeType = LikeType.LIKE


# Bookmark схемы
class BookmarkBase(BaseSchema):
    user: UserBase
    article: ArticleBase


class BookmarkCreate(Schema):
    article_id: int


# Search схемы
class SearchQuery(Schema):
    q: constr(min_length=2, max_length=100)
    category: Optional[str] = None
    tag: Optional[str] = None
    author: Optional[str] = None
    status: Optional[ArticleStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    ordering: Optional[str] = None
    page: int = 1
    page_size: int = 10
    
    @validator('ordering')
    def validate_ordering(cls, v):
        if v:
            allowed = ['created_at', 'published_at', 'view_count', 'like_count', 'comment_count']
            field = v.lstrip('-')
            if field not in allowed:
                raise ValueError(f'Invalid ordering field. Allowed: {", ".join(allowed)}')
        return v


# Error схемы
class ErrorResponse(Schema):
    detail: str
    code: Optional[str] = None
    errors: Optional[Dict[str, List[str]]] = None


class ValidationErrorResponse(Schema):
    detail: List[Dict[str, Any]]


# Statistics схемы
class StatisticsResponse(Schema):
    total_articles: int
    total_users: int
    total_comments: int
    total_categories: int
    popular_articles: List[Dict[str, Any]]
    recent_articles: List[Dict[str, Any]]
    active_users: List[Dict[str, Any]]
    categories_stats: List[Dict[str, Any]]


# Health check схема
class HealthCheckResponse(Schema):
    status: str
    timestamp: datetime
    database: bool
    redis: bool
    celery: bool


# Создаем схемы на основе моделей
UserSchema = create_schema(
    User,
    name='UserSchema',
    fields=['id', 'username', 'email', 'first_name', 'last_name', 'bio', 'avatar_url']
)

CategorySchema = create_schema(
    Category,
    name='CategorySchema',
    fields=['id', 'name', 'slug', 'description', 'article_count']
)

TagSchema = create_schema(
    Tag,
    name='TagSchema',
    fields=['id', 'name', 'slug', 'description', 'usage_count']
)

ArticleSchema = create_schema(
    Article,
    name='ArticleSchema',
    fields=['id', 'title', 'slug', 'excerpt', 'status', 'view_count', 'published_at']
)
