from ninja import Schema
from typing import Optional
from datetime import datetime

class CommentIn(Schema):
    content: str
    parent_id: Optional[str] = None

class CommentUpdate(Schema):
    content: str

class CommentOut(Schema):
    id: str
    content: str
    author: 'UserOut'
    article: 'ArticleOut'
    parent: Optional['CommentOut'] = None
    is_approved: bool
    created_at: datetime
    updated_at: datetime
    replies: Optional[list['CommentOut']] = None