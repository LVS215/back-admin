import pytest
from django.test import Client
from django.contrib.auth.models import User
from ninja.testing import TestClient
import factory
from factory.django import DjangoModelFactory

# Фабрики для тестовых данных
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'testuser{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')

class SuperUserFactory(UserFactory):
    is_staff = True
    is_superuser = True

# Фикстуры
@pytest.fixture
def api_client():
    return TestClient(api.router)

@pytest.fixture
def user():
    return UserFactory()

@pytest.fixture
def admin_user():
    return SuperUserFactory()

@pytest.fixture
def authenticated_client(user):
    client = TestClient(api.router)
    # Здесь нужно добавить токен в заголовки
    return client

@pytest.fixture
def token(user):
    from core.models import AuthToken
    token = AuthToken.generate_token()
    return AuthToken.objects.create(user=user, token=token)

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Даем доступ к БД всем тестам"""
    pass
