from ninja import Schema
from typing import Optional
from datetime import datetime

class CategoryIn(Schema):
    name: str
    slug: str
    description: Optional[str] = None

class CategoryOut(Schema):
    id: str
    name: str
    slug: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

class ArticleIn(Schema):
    title: str
    slug: str
    content: str
    excerpt: Optional[str] = None
    category_slug: Optional[str] = None
    status: str = "draft"

class ArticleUpdate(Schema):
    title: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    category_slug: Optional[str] = None
    status: Optional[str] = None

class ArticleOut(Schema):
    id: str
    title: str
    slug: str
    content: str
    excerpt: Optional[str]
    author: 'UserOut'
    category: Optional[CategoryOut] = None
    status: str
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime