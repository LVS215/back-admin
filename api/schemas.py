from ninja import Schema
from datetime import datetime
from typing import List, Optional

class UserRegisterSchema(Schema):
    username: str
    email: str
    password: str

class UserLoginSchema(Schema):
    username: str
    password: str

class UserOutSchema(Schema):
    id: int
    username: str
    email: str
    date_joined: datetime
    
    @staticmethod
    def from_orm(user):
        return UserOutSchema(
            id=user.id,
            username=user.username,
            email=user.email,
            date_joined=user.date_joined
        )

class TokenResponseSchema(Schema):
    message: str
    token: str
    user: UserOutSchema

class CategorySchema(Schema):
    id: int
    name: str
    slug: str
    description: Optional[str] = None

class PostCreateSchema(Schema):
    title: str
    content: str
    excerpt: Optional[str] = None
    category_id: Optional[int] = None
    status: str = "draft"

class PostUpdateSchema(Schema):
    title: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    category_id: Optional[int] = None
    status: Optional[str] = None

class PostOutSchema(Schema):
    id: int
    title: str
    slug: str
    content: str
    excerpt: Optional[str] = None
    author: UserOutSchema
    category: Optional[CategorySchema] = None
    status: str
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    view_count: int

class CommentCreateSchema(Schema):
    content: str
    post_id: int
    parent_id: Optional[int] = None

class CommentUpdateSchema(Schema):
    content: str

class CommentOutSchema(Schema):
    id: int
    content: str
    author: UserOutSchema
    post_id: int
    parent_id: Optional[int] = None
    is_approved: bool
    created_at: datetime
    updated_at: datetime
