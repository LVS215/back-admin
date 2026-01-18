import pytest
import json
from datetime import datetime, timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from ninja.testing import TestClient

from core.models import User, Category, Article, Comment, Like, Bookmark
from blog.urls import api


@pytest.fixture
def api_client():
    """
    Фикстура для API клиента
    """
    return TestClient(api)


@pytest.fixture
def django_client():
    """
    Фикстура для Django REST Framework клиента
    """
    return APIClient()


@pytest.fixture
def test_user():
    """
    Фикстура для тестового пользователя
    """
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123',
        is_verified=True
    )


@pytest.fixture
def test_admin():
    """
    Фикстура для тестового администратора
    """
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )


@pytest.fixture
def test_category():
    """
    Фикстура для тестовой категории
    """
    return Category.objects.create(
        name='Test Category',
        slug='test-category',
        description='Test category description'
    )


@pytest.fixture
def test_article(test_user, test_category):
    """
    Фикстура для тестовой статьи
    """
    return Article.objects.create(
        title='Test Article',
        slug='test-article',
        content='Test article content',
        author=test_user,
        category=test_category,
        status='published',
        published_at=timezone.now()
    )


class TestHealthCheckAPI:
    """
    Тесты для health check endpoints
    """
    
    def test_health_check(self, api_client):
        """
        Тестирование health check endpoint
        """
        response = api_client.get('/api/health/')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'healthy'
        assert 'timestamp' in response.json()


class TestAuthenticationAPI:
    """
    Тесты для аутентификации
    """
    
    def test_register_success(self, api_client):
        """
        Тестирование успешной регистрации
        """
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'password_confirm': 'newpass123',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = api_client.post('/api/auth/register', json=data)
        assert response.status_code == status.HTTP_201_CREATED
        
        response_data = response.json()
        assert 'access' in response_data
        assert 'refresh' in response_data
        assert 'user' in response_data
        assert response_data['user']['username'] == 'newuser'
        assert response_data['user']['email'] == 'newuser@example.com'
        
        # Проверяем создание пользователя в БД
        user = User.objects.filter(username='newuser').first()
        assert user is not None
        assert user.email == 'newuser@example.com'
        assert user.check_password('newpass123')
    
    def test_register_duplicate_email(self, api_client, test_user):
        """
        Тестирование регистрации с существующим email
        """
        data = {
            'username': 'anotheruser',
            'email': test_user.email,
            'password': 'testpass123',
            'password_confirm': 'testpass123'
        }
        
        response = api_client.post('/api/auth/register', json=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'email_exists'
    
    def test_register_duplicate_username(self, api_client, test_user):
        """
        Тестирование регистрации с существующим username
        """
        data = {
            'username': test_user.username,
            'email': 'another@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123'
        }
        
        response = api_client.post('/api/auth/register', json=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'username_exists'
    
    def test_register_password_mismatch(self, api_client):
        """
        Тестирование регистрации с несовпадающими паролями
        """
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'password123',
            'password_confirm': 'different123'
        }
        
        response = api_client.post('/api/auth/register', json=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'passwords do not match' in str(response.json()['detail'])
    
    def test_login_success(self, api_client, test_user):
        """
        Тестирование успешного входа
        """
        data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        
        response = api_client.post('/api/auth/login', json=data)
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert 'access' in response_data
        assert 'refresh' in response_data
        assert 'user' in response_data
        assert response_data['user']['id'] == test_user.id
    
    def test_login_invalid_credentials(self, api_client):
        """
        Тестирование входа с неверными учетными данными
        """
        data = {
            'email': 'nonexistent@example.com',
            'password': 'wrongpassword'
        }
        
        response = api_client.post('/api/auth/login', json=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'invalid_credentials'
    
    def test_refresh_token(self, api_client, test_user):
        """
        Тестирование обновления токена
        """
        # Сначала логинимся
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        refresh_token = login_response.json()['refresh']
        
        # Обновляем токен
        response = api_client.post('/api/auth/refresh', json={'refresh': refresh_token})
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.json()
    
    def test_logout(self, api_client, test_user):
        """
        Тестирование выхода
        """
        # Логинимся
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        refresh_token = login_response.json()['refresh']
        
        # Выходим
        response = api_client.post('/api/auth/logout', json={'refresh': refresh_token})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['detail'] == 'Successfully logged out'
        
        # Пытаемся обновить токен после выхода
        refresh_response = api_client.post('/api/auth/refresh', json={'refresh': refresh_token})
        assert refresh_response.status_code == status.HTTP_400_BAD_REQUEST


class TestUserAPI:
    """
    Тесты для пользовательских endpoints
    """
    
    def test_get_current_user_authenticated(self, api_client, test_user):
        """
        Тестирование получения информации о текущем пользователе (аутентифицированный)
        """
        # Получаем токен
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        # Получаем информацию о пользователе
        headers = {'Authorization': f'Bearer {access_token}'}
        response = api_client.get('/api/users/me', headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['id'] == test_user.id
        assert response_data['username'] == test_user.username
        assert response_data['email'] == test_user.email
    
    def test_get_current_user_unauthenticated(self, api_client):
        """
        Тестирование получения информации о текущем пользователе (неаутентифицированный)
        """
        response = api_client.get('/api/users/me')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_update_current_user(self, api_client, test_user):
        """
        Тестирование обновления информации о текущем пользователе
        """
        # Получаем токен
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        # Обновляем информацию
        headers = {'Authorization': f'Bearer {access_token}'}
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'bio': 'Updated bio'
        }
        
        response = api_client.put('/api/users/me', json=update_data, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data['first_name'] == 'Updated'
        assert response_data['last_name'] == 'Name'
        assert response_data['bio'] == 'Updated bio'
        
        # Проверяем обновление в БД
        test_user.refresh_from_db()
        assert test_user.first_name == 'Updated'
        assert test_user.last_name == 'Name'
        assert test_user.bio == 'Updated bio'
    
    def test_change_password(self, api_client, test_user):
        """
        Тестирование смены пароля
        """
        # Получаем токен
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        # Меняем пароль
        headers = {'Authorization': f'Bearer {access_token}'}
        password_data = {
            'current_password': 'testpass123',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123'
        }
        
        response = api_client.post('/api/users/me/change-password', json=password_data, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем, что новый пароль работает
        new_login_data = {
            'email': test_user.email,
            'password': 'newpass123'
        }
        new_login_response = api_client.post('/api/auth/login', json=new_login_data)
        assert new_login_response.status_code == status.HTTP_200_OK
    
    def test_change_password_wrong_current(self, api_client, test_user):
        """
        Тестирование смены пароля с неверным текущим паролем
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        password_data = {
            'current_password': 'wrongpassword',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123'
        }
        
        response = api_client.post('/api/users/me/change-password', json=password_data, headers=headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'incorrect_password'
    
    def test_get_user_by_id(self, api_client, test_user):
        """
        Тестирование получения информации о пользователе по ID
        """
        response = api_client.get(f'/api/users/{test_user.id}')
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data['id'] == test_user.id
        assert response_data['username'] == test_user.username


class TestCategoryAPI:
    """
    Тесты для категорий
    """
    
    def test_list_categories(self, api_client, test_category):
        """
        Тестирование получения списка категорий
        """
        response = api_client.get('/api/categories/')
        assert response.status_code == status.HTTP_200_OK
        
        categories = response.json()
        assert len(categories) >= 1
        assert any(cat['name'] == 'Test Category' for cat in categories)
    
    def test_get_category_by_slug(self, api_client, test_category):
        """
        Тестирование получения категории по slug
        """
        response = api_client.get(f'/api/categories/{test_category.slug}')
        assert response.status_code == status.HTTP_200_OK
        
        category = response.json()
        assert category['name'] == 'Test Category'
        assert category['slug'] == 'test-category'
    
    def test_create_category_authenticated(self, api_client, test_admin):
        """
        Тестирование создания категории (аутентифицированный администратор)
        """
        # Получаем токен администратора
        login_data = {
            'email': test_admin.email,
            'password': 'adminpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        # Создаем категорию
        headers = {'Authorization': f'Bearer {access_token}'}
        category_data = {
            'name': 'New Category',
            'description': 'New category description',
            'color': '#ff0000',
            'is_active': True
        }
        
        response = api_client.post('/api/categories/', json=category_data, headers=headers)
        assert response.status_code == status.HTTP_201_CREATED
        
        response_data = response.json()
        assert response_data['name'] == 'New Category'
        assert response_data['slug'] == 'new-category'
        
        # Проверяем создание в БД
        category = Category.objects.filter(name='New Category').first()
        assert category is not None
        assert category.description == 'New category description'
    
    def test_create_category_unauthenticated(self, api_client):
        """
        Тестирование создания категории (неаутентифицированный)
        """
        category_data = {
            'name': 'New Category',
            'description': 'New category description'
        }
        
        response = api_client.post('/api/categories/', json=category_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_create_category_regular_user(self, api_client, test_user):
        """
        Тестирование создания категории обычным пользователем
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        category_data = {
            'name': 'New Category',
            'description': 'New category description'
        }
        
        response = api_client.post('/api/categories/', json=category_data, headers=headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_update_category(self, api_client, test_category, test_admin):
        """
        Тестирование обновления категории
        """
        login_data = {
            'email': test_admin.email,
            'password': 'adminpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        update_data = {
            'name': 'Updated Category',
            'description': 'Updated description'
        }
        
        response = api_client.put(f'/api/categories/{test_category.id}', json=update_data, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data['name'] == 'Updated Category'
        assert response_data['description'] == 'Updated description'
        
        # Проверяем обновление в БД
        test_category.refresh_from_db()
        assert test_category.name == 'Updated Category'
        assert test_category.description == 'Updated description'
    
    def test_delete_category(self, api_client, test_category, test_admin):
        """
        Тестирование удаления категории
        """
        login_data = {
            'email': test_admin.email,
            'password': 'adminpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        response = api_client.delete(f'/api/categories/{test_category.id}', headers=headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Проверяем удаление из БД
        category_exists = Category.objects.filter(id=test_category.id).exists()
        assert not category_exists


class TestArticleAPI:
    """
    Тесты для статей
    """
    
    def test_list_articles(self, api_client, test_article):
        """
        Тестирование получения списка статей
        """
        response = api_client.get('/api/articles/')
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert 'count' in response_data
        assert 'results' in response_data
        assert response_data['count'] >= 1
        
        # Проверяем, что наша статья есть в списке
        articles = response_data['results']
        assert any(article['title'] == 'Test Article' for article in articles)
    
    def test_get_article_by_slug(self, api_client, test_article):
        """
        Тестирование получения статьи по slug
        """
        response = api_client.get(f'/api/articles/{test_article.slug}')
        assert response.status_code == status.HTTP_200_OK
        
        article = response.json()
        assert article['title'] == 'Test Article'
        assert article['slug'] == 'test-article'
        assert article['content'] == 'Test article content'
        assert article['author']['username'] == test_article.author.username
    
    def test_create_article_authenticated(self, api_client, test_user, test_category):
        """
        Тестирование создания статьи (аутентифицированный)
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        article_data = {
            'title': 'New Article',
            'content': 'This is the content of the new article.',
            'category_id': test_category.id,
            'status': 'draft'
        }
        
        response = api_client.post('/api/articles/', json=article_data, headers=headers)
        assert response.status_code == status.HTTP_201_CREATED
        
        response_data = response.json()
        assert response_data['title'] == 'New Article'
        assert response_data['status'] == 'draft'
        assert response_data['author']['id'] == test_user.id
        
        # Проверяем создание в БД
        article = Article.objects.filter(title='New Article').first()
        assert article is not None
        assert article.author == test_user
        assert article.category == test_category
    
    def test_create_article_unauthenticated(self, api_client):
        """
        Тестирование создания статьи (неаутентифицированный)
        """
        article_data = {
            'title': 'New Article',
            'content': 'Article content'
        }
        
        response = api_client.post('/api/articles/', json=article_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_update_article_owner(self, api_client, test_article, test_user):
        """
        Тестирование обновления статьи владельцем
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        update_data = {
            'title': 'Updated Article',
            'content': 'Updated content'
        }
        
        response = api_client.put(f'/api/articles/{test_article.id}', json=update_data, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data['title'] == 'Updated Article'
        assert response_data['content'] == 'Updated content'
        
        # Проверяем обновление в БД
        test_article.refresh_from_db()
        assert test_article.title == 'Updated Article'
        assert test_article.content == 'Updated content'
    
    def test_update_article_non_owner(self, api_client, test_article):
        """
        Тестирование обновления статьи не-владельцем
        """
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        login_data = {
            'email': other_user.email,
            'password': 'otherpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        update_data = {
            'title': 'Unauthorized Update'
        }
        
        response = api_client.put(f'/api/articles/{test_article.id}', json=update_data, headers=headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_article_owner(self, api_client, test_article, test_user):
        """
        Тестирование удаления статьи владельцем
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        response = api_client.delete(f'/api/articles/{test_article.id}', headers=headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Проверяем удаление из БД
        article_exists = Article.objects.filter(id=test_article.id).exists()
        assert not article_exists
    
    def test_like_article(self, api_client, test_article, test_user):
        """
        Тестирование лайка статьи
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Лайкаем статью
        response = api_client.post(f'/api/articles/{test_article.id}/like', headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['detail'] == 'Article liked successfully'
        
        # Проверяем лайк в БД
        like_exists = Like.objects.filter(user=test_user, article=test_article).exists()
        assert like_exists
        
        # Убираем лайк
        response = api_client.post(f'/api/articles/{test_article.id}/like', headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['detail'] == 'Article like removed'
        
        # Проверяем, что лайк удален
        like_exists = Like.objects.filter(user=test_user, article=test_article).exists()
        assert not like_exists


class TestCommentAPI:
    """
    Тесты для комментариев
    """
    
    @pytest.fixture
    def test_comment(self, test_article, test_user):
        """
        Фикстура для тестового комментария
        """
        return Comment.objects.create(
            article=test_article,
            author=test_user,
            content='Test comment content',
            status='approved'
        )
    
    def test_list_comments(self, api_client, test_article, test_comment):
        """
        Тестирование получения списка комментариев
        """
        response = api_client.get(f'/api/comments/article/{test_article.id}')
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert 'count' in response_data
        assert response_data['count'] >= 1
        
        comments = response_data['results']
        assert any(comment['content'] == 'Test comment content' for comment in comments)
    
    def test_create_comment(self, api_client, test_article, test_user):
        """
        Тестирование создания комментария
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        comment_data = {
            'article_id': test_article.id,
            'content': 'New comment content'
        }
        
        response = api_client.post('/api/comments/', json=comment_data, headers=headers)
        assert response.status_code == status.HTTP_201_CREATED
        
        response_data = response.json()
        assert response_data['content'] == 'New comment content'
        assert response_data['author']['id'] == test_user.id
        
        # Проверяем создание в БД
        comment = Comment.objects.filter(content='New comment content').first()
        assert comment is not None
        assert comment.article == test_article
        assert comment.author == test_user
    
    def test_create_comment_unauthenticated(self, api_client, test_article):
        """
        Тестирование создания комментария (неаутентифицированный)
        """
        comment_data = {
            'article_id': test_article.id,
            'content': 'New comment'
        }
        
        response = api_client.post('/api/comments/', json=comment_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_update_comment_owner(self, api_client, test_comment, test_user):
        """
        Тестирование обновления комментария владельцем
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        update_data = {
            'content': 'Updated comment content',
            'edit_reason': 'Fixed typo'
        }
        
        response = api_client.put(f'/api/comments/{test_comment.id}', json=update_data, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data['content'] == 'Updated comment content'
        assert response_data['is_edited'] is True
        
        # Проверяем обновление в БД
        test_comment.refresh_from_db()
        assert test_comment.content == 'Updated comment content'
        assert test_comment.is_edited is True
        assert test_comment.edit_reason == 'Fixed typo'
    
    def test_delete_comment_owner(self, api_client, test_comment, test_user):
        """
        Тестирование удаления комментария владельцем
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        response = api_client.delete(f'/api/comments/{test_comment.id}', headers=headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Проверяем удаление из БД
        comment_exists = Comment.objects.filter(id=test_comment.id).exists()
        assert not comment_exists


class TestSearchAPI:
    """
    Тесты для поиска
    """
    
    def test_search_articles(self, api_client, test_article):
        """
        Тестирование поиска статей
        """
        response = api_client.get('/api/search/', params={'q': 'Test'})
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert 'count' in response_data
        assert response_data['count'] >= 1
        
        articles = response_data['results']
        assert any(article['title'] == 'Test Article' for article in articles)
    
    def test_search_no_results(self, api_client):
        """
        Тестирование поиска без результатов
        """
        response = api_client.get('/api/search/', params={'q': 'nonexistentterm'})
        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.json()
        assert response_data['count'] == 0


class TestStatisticsAPI:
    """
    Тесты для статистики
    """
    
    def test_get_statistics_admin(self, api_client, test_admin):
        """
        Тестирование получения статистики администратором
        """
        login_data = {
            'email': test_admin.email,
            'password': 'adminpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        response = api_client.get('/api/stats/', headers=headers)
        assert response.status_code == status.HTTP_200_OK
        
        stats = response.json()
        assert 'total_articles' in stats
        assert 'total_users' in stats
        assert 'total_comments' in stats
        assert 'popular_articles' in stats
    
    def test_get_statistics_regular_user(self, api_client, test_user):
        """
        Тестирование получения статистики обычным пользователем
        """
        login_data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post('/api/auth/login', json=login_data)
        access_token = login_response.json()['access']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        response = api_client.get('/api/stats/', headers=headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestIntegration:
    """
    Интеграционные тесты
    """
    
    def test_full_article_workflow(self, api_client):
        """
        Полный тест рабочего процесса статьи:
        1. Регистрация пользователя
        2. Создание категории (администратором)
        3. Создание статьи
        4. Публикация статьи
        5. Добавление комментария
        6. Лайк статьи
        7. Поиск статьи
        """
        # 1. Регистрация пользователя
        register_data = {
            'username': 'workflowuser',
            'email': 'workflow@example.com',
            'password': 'workflow123',
            'password_confirm': 'workflow123'
        }
        register_response = api_client.post('/api/auth/register', json=register_data)
        assert register_response.status_code == status.HTTP_201_CREATED
        
        access_token = register_response.json()['access']
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Создаем администратора для создания категории
        admin = User.objects.create_superuser(
            username='workflowadmin',
            email='admin@workflow.com',
            password='admin123'
        )
        
        # 2. Создание категории (администратором)
        admin_login_data = {
            'email': admin.email,
            'password': 'admin123'
        }
        admin_login_response = api_client.post('/api/auth/login', json=admin_login_data)
        admin_access_token = admin_login_response.json()['access']
        admin_headers = {'Authorization': f'Bearer {admin_access_token}'}
        
        category_data = {
            'name': 'Workflow Category',
            'description': 'Category for workflow testing'
        }
        category_response = api_client.post('/api/categories/', json=category_data, headers=admin_headers)
        assert category_response.status_code == status.HTTP_201_CREATED
        category_id = category_response.json()['id']
        
        # 3. Создание статьи
        article_data = {
            'title': 'Workflow Test Article',
            'content': 'This is a test article for workflow testing.',
            'category_id': category_id,
            'status': 'draft'
        }
        article_response = api_client.post('/api/articles/', json=article_data, headers=headers)
        assert article_response.status_code == status.HTTP_201_CREATED
        article_id = article_response.json()['id']
        
        # 4. Публикация статьи
        publish_data = {
            'status': 'published'
        }
        publish_response = api_client.put(f'/api/articles/{article_id}', json=publish_data, headers=headers)
        assert publish_response.status_code == status.HTTP_200_OK
        assert publish_response.json()['status'] == 'published'
        
        # 5. Добавление комментария
        comment_data = {
            'article_id': article_id,
            'content': 'Great article!'
        }
        comment_response = api_client.post('/api/comments/', json=comment_data, headers=headers)
        assert comment_response.status_code == status.HTTP_201_CREATED
        
        # 6. Лайк статьи
        like_response = api_client.post(f'/api/articles/{article_id}/like', headers=headers)
        assert like_response.status_code == status.HTTP_200_OK
        
        # 7. Поиск статьи
        search_response = api_client.get('/api/search/', params={'q': 'Workflow'})
        assert search_response.status_code == status.HTTP_200_OK
        assert search_response.json()['count'] >= 1
        
        print("✅ Full workflow test passed successfully!")
