from ninja import Schema
from datetime import datetime
from typing import Optional, List

class UserSchema(Schema):
    id: int
    username: str
    email: Optional[str] = None

class UserCreate(Schema):
    username: str
    password: str
    email: Optional[str] = None

class UserLogin(Schema):
    username: str
    password: str

class TokenResponse(Schema):
    token: str
    user: UserSchema

class CategorySchema(Schema):
    id: int
    name: str
    slug: str

class ArticleSchema(Schema):
    id: int
    title: str
    content: str
    author: UserSchema
    category: Optional[CategorySchema] = None
    created_at: datetime
    updated_at: datetime
    is_published: bool

class ArticleCreate(Schema):
    title: str
    content: str
    category_id: Optional[int] = None
    is_published: bool = True

class ArticleUpdate(Schema):
    title: Optional[str] = None
    content: Optional[str] = None
    category_id: Optional[int] = None
    is_published: Optional[bool] = None

class CommentSchema(Schema):
    id: int
    article_id: int
    author: UserSchema
    content: str
    created_at: datetime
    updated_at: datetime
    parent_id: Optional[int] = None

class CommentCreate(Schema):
    article_id: int
    content: str
    parent_id: Optional[int] = None

class CommentUpdate(Schema):
    content: str

class ErrorResponse(Schema):
    detail: str
