import pytest
from django.test import Client
from django.contrib.auth.models import User
from ninja.testing import TestClient
import factory
from factory.django import DjangoModelFactory

from blog.urls import api
from core.models import Category, Post, Comment, AuthToken, UserProfile

# Фабрики
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'testuser{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpassword123')
    is_active = True

class SuperUserFactory(UserFactory):
    is_staff = True
    is_superuser = True

class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    
    name = factory.Sequence(lambda n: f'Category {n}')
    slug = factory.Sequence(lambda n: f'category-{n}')

class PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    
    title = factory.Sequence(lambda n: f'Test Post {n}')
    content = factory.Faker('paragraph')
    author = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)
    status = Post.STATUS_PUBLISHED

class CommentFactory(DjangoModelFactory):
    class Meta:
        model = Comment
    
    content = factory.Faker('sentence')
    author = factory.SubFactory(UserFactory)
    post = factory.SubFactory(PostFactory)
    is_approved = True

# Фикстуры
@pytest.fixture
def api_client():
    """API клиент Django Ninja"""
    return TestClient(api)

@pytest.fixture
def django_client():
    """Django тестовый клиент"""
    return Client()

@pytest.fixture
def user():
    """Создает обычного пользователя"""
    user = UserFactory()
    UserProfile.objects.create(user=user)
    return user

@pytest.fixture
def admin_user():
    """Создает администратора"""
    admin = SuperUserFactory()
    UserProfile.objects.create(user=admin)
    return admin

@pytest.fixture
def category():
    """Создает категорию"""
    return CategoryFactory()

@pytest.fixture
def post(user, category):
    """Создает статью"""
    return PostFactory(author=user, category=category)

@pytest.fixture
def comment(user, post):
    """Создает комментарий"""
    return CommentFactory(author=user, post=post)

@pytest.fixture
def auth_token(user):
    """Создает токен аутентификации"""
    token = AuthToken.generate_token()
    return AuthToken.objects.create(
        user=user,
        token=token,
        name="Test Token"
    )

@pytest.fixture
def authenticated_client(api_client, auth_token):
    """Клиент с аутентификацией"""
    api_client.headers['Authorization'] = f'Bearer {auth_token.token}'
    return api_client

@pytest.fixture
def admin_client(api_client, admin_user):
    """Клиент с правами администратора"""
    token = AuthToken.generate_token()
    auth_token = AuthToken.objects.create(user=admin_user, token=token)
    api_client.headers['Authorization'] = f'Bearer {token}'
    return api_client

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Разрешает доступ к БД для всех тестов"""
    pass

@pytest.fixture(autouse=True)
def setup_logging():
    """Настройка логирования для тестов"""
    import logging
    logging.getLogger('django').setLevel(logging.ERROR)
    logging.getLogger('api').setLevel(logging.ERROR)
    logging.getLogger('core').setLevel(logging.ERROR)

# Хелперы для тестов
class TestHelpers:
    @staticmethod
    def assert_response_ok(response, expected_status=200):
        assert response.status_code == expected_status
        return response.json()
    
    @staticmethod
    def assert_response_error(response, expected_status=400):
        assert response.status_code == expected_status
        data = response.json()
        assert 'detail' in data
        return data
    
    @staticmethod
    def assert_token_valid(token):
        assert len(token) == 256
        assert isinstance(token, str)
    
    @staticmethod
    def create_test_posts(count=5, author=None, **kwargs):
        """Создание нескольких тестовых статей"""
        posts = []
        for i in range(count):
            post = PostFactory(
                title=f'Test Post {i}',
                author=author,
                **kwargs
            )
            posts.append(post)
        return posts

# Регистрируем хелперы
@pytest.fixture
def helpers():
    return TestHelpers
