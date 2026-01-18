import pytest
from django.test import Client
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from model_bakery import baker
from core.models import Post, Category, Tag, Comment

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user():
    return baker.make(User, username='testuser', email='test@example.com')

@pytest.fixture
def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client

@pytest.fixture
def category():
    return baker.make(Category, name='Technology')

@pytest.fixture
def tag():
    return baker.make(Tag, name='python')

@pytest.fixture
def post(user, category):
    post = baker.make(Post, author=user, category=category, status='published')
    post.tags.add(baker.make(Tag, name='django'))
    return post

@pytest.fixture
def comment(user, post):
    return baker.make(Comment, post=post, author=user, is_approved=True)

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass
