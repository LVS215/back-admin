from ninja import Schema
from typing import Optional
from datetime import datetime

class UserIn(Schema):
    username: str
    password: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserOut(Schema):
    id: str
    username: str
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    date_joined: datetime
    last_login: Optional[datetime]

class AuthIn(Schema):
    username: str
    password: str

class TokenOut(Schema):
    access: str
    refresh: str
    user: UserOut