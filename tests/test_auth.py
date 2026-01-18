import pytest
from django.contrib.auth.models import User
from ninja.testing import TestClient

from blog.urls import api
from core.models import AuthToken, UserProfile

class TestAuthenticationAPI:
    """Тесты аутентификации и регистрации"""
    
    def test_register_success(self, api_client, helpers):
        """Тест успешной регистрации пользователя"""
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!"
        }
        
        response = api_client.post("/api/auth/register", json=data)
        result = helpers.assert_response_ok(response)
        
        # Проверяем ответ
        assert result["message"] == "User registered successfully"
        helpers.assert_token_valid(result["token"])
        assert result["token_length"] == 256
        assert result["user"]["username"] == "newuser"
        assert result["user"]["email"] == "newuser@example.com"
        
        # Проверяем, что пользователь создан в БД
        user = User.objects.get(username="newuser")
        assert user.email == "newuser@example.com"
        assert UserProfile.objects.filter(user=user).exists()
        
        # Проверяем, что токен создан
        token = AuthToken.objects.get(token=result["token"])
        assert token.user == user
        assert token.is_active is True
    
    def test_register_duplicate_username(self, api_client, user, helpers):
        """Тест регистрации с существующим username"""
        data = {
            "username": user.username,
            "email": "different@example.com",
            "password": "password123",
            "password_confirm": "password123"
        }
        
        response = api_client.post("/api/auth/register", json=data)
        result = helpers.assert_response_error(response, 400)
        
        assert result["detail"] == "Username already exists"
        assert result["code"] == "username_exists"
    
    def test_register_duplicate_email(self, api_client, user, helpers):
        """Тест регистрации с существующим email"""
        data = {
            "username": "differentuser",
            "email": user.email,
            "password": "password123",
            "password_confirm": "password123"
        }
        
        response = api_client.post("/api/auth/register", json=data)
        result = helpers.assert_response_error(response, 400)
        
        assert result["detail"] == "Email already exists"
        assert result["code"] == "email_exists"
    
    def test_register_password_too_short(self, api_client, helpers):
        """Тест регистрации с коротким паролем"""
        data = {
            "username": "shortpass",
            "email": "short@example.com",
            "password": "123",
            "password_confirm": "123"
        }
        
        response = api_client.post("/api/auth/register", json=data)
        result = helpers.assert_response_error(response, 400)
        
        assert result["detail"] == "Password must be at least 8 characters long"
        assert result["code"] == "password_too_short"
    
    def test_register_password_mismatch(self, api_client, helpers):
        """Тест регистрации с несовпадающими паролями"""
        data = {
            "username": "mismatch",
            "email": "mismatch@example.com",
            "password": "password123",
            "password_confirm": "different123"
        }
        
        response = api_client.post("/api/auth/register", json=data)
        result = helpers.assert_response_error(response, 400)
        
        assert result["detail"] == "Passwords do not match"
        assert result["code"] == "passwords_mismatch"
    
    def test_login_success(self, api_client, user, helpers):
        """Тест успешного входа"""
        # Устанавливаем пароль
        user.set_password("testpassword123")
        user.save()
        
        data = {
            "username": user.username,
            "password": "testpassword123"
        }
        
        response = api_client.post("/api/auth/login", json=data)
        result = helpers.assert_response_ok(response)
        
        assert result["message"] == "Login successful"
        helpers.assert_token_valid(result["token"])
        assert result["token_length"] == 256
        assert result["user"]["username"] == user.username
        assert result["user"]["email"] == user.email
    
    def test_login_wrong_password(self, api_client, user, helpers):
        """Тест входа с неверным паролем"""
        user.set_password("correctpassword")
        user.save()
        
        data = {
            "username": user.username,
            "password": "wrongpassword"
        }
        
        response = api_client.post("/api/auth/login", json=data)
        assert response.status_code == 401
        result = response.json()
        assert "detail" in result
        assert "Invalid username or password" in result["detail"]
    
    def test_login_nonexistent_user(self, api_client, helpers):
        """Тест входа несуществующего пользователя"""
        data = {
            "username": "nonexistent",
            "password": "password123"
        }
        
        response = api_client.post("/api/auth/login", json=data)
        assert response.status_code == 401
    
    def test_login_inactive_user(self, api_client, user, helpers):
        """Тест входа неактивного пользователя"""
        user.is_active = False
        user.set_password("testpassword123")
        user.save()
        
        data = {
            "username": user.username,
            "password": "testpassword123"
        }
        
        response = api_client.post("/api/auth/login", json=data)
        assert response.status_code == 401
        result = response.json()
        assert "User account is inactive" in result["detail"]
    
    def test_get_profile_authenticated(self, authenticated_client, user, helpers):
        """Тест получения профиля аутентифицированным пользователем"""
        response = authenticated_client.get("/api/auth/profile")
        result = helpers.assert_response_ok(response)
        
        assert result["username"] == user.username
        assert result["email"] == user.email
        assert result["id"] == user.id
        assert "date_joined" in result
        assert "is_active" in result
        assert "is_staff" in result
    
    def test_get_profile_unauthenticated(self, api_client, helpers):
        """Тест получения профиля без аутентификации"""
        response = api_client.get("/api/auth/profile")
        assert response.status_code == 401
    
    def test_logout_success(self, authenticated_client, auth_token, helpers):
        """Тест успешного выхода"""
        response = authenticated_client.post("/api/auth/logout")
        result = helpers.assert_response_ok(response)
        
        assert result["message"] == "Logged out successfully"
        
        # Проверяем, что токен деактивирован
        auth_token.refresh_from_db()
        assert auth_token.is_active is False
    
    def test_logout_unauthenticated(self, api_client, helpers):
        """Тест выхода без аутентификации"""
        response = api_client.post("/api/auth/logout")
        assert response.status_code == 401
    
    def test_revoke_all_tokens(self, authenticated_client, user, helpers):
        """Тест отзыва всех токенов"""
        # Создаем несколько токенов
        tokens = []
        for i in range(3):
            token = AuthToken.generate_token()
            tokens.append(AuthToken.objects.create(
                user=user,
                token=token,
                name=f"Token {i}"
            ))
        
        data = {
            "reason": "security_concern"
        }
        
        response = authenticated_client.post("/api/auth/revoke-all", json=data)
        result = helpers.assert_response_ok(response)
        
        assert result["message"] == "All tokens have been revoked"
        
        # Проверяем, что все токены деактивированы
        for token in tokens:
            token.refresh_from_db()
            assert token.is_active is False
    
    def test_list_tokens(self, authenticated_client, user, helpers):
        """Тест получения списка токенов"""
        # Создаем несколько токенов
        for i in range(3):
            token = AuthToken.generate_token()
            AuthToken.objects.create(
                user=user,
                token=token,
                name=f"Token {i}"
            )
        
        response = authenticated_client.get("/api/auth/tokens")
        result = helpers.assert_response_ok(response)
        
        assert "tokens" in result
        assert len(result["tokens"]) >= 3  # Включая токен аутентификации
        
        for token_data in result["tokens"]:
            assert "id" in token_data
            assert "name" in token_data
            assert "created_at" in token_data
            assert "last_used" in token_data
            assert "expires_at" in token_data
    
    def test_token_length_exactly_256(self, api_client, helpers):
        """Тест что токен всегда имеет длину 256 символов"""
        data = {
            "username": "tokenuser",
            "email": "token@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!"
        }
        
        response = api_client.post("/api/auth/register", json=data)
        result = helpers.assert_response_ok(response)
        
        token = result["token"]
        assert len(token) == 256
        assert result["token_length"] == 256
    
    def test_token_authentication_header(self, api_client, user):
        """Тест аутентификации через заголовок Authorization"""
        # Создаем токен
        token = AuthToken.generate_token()
        auth_token = AuthToken.objects.create(user=user, token=token)
        
        # Делаем запрос с заголовком Authorization
        client = TestClient(api)
        client.headers['Authorization'] = f'Bearer {token}'
        
        response = client.get("/api/auth/profile")
        assert response.status_code == 200
        
        result = response.json()
        assert result["username"] == user.username
    
    def test_token_authentication_invalid_token(self, api_client):
        """Тест аутентификации с неверным токеном"""
        client = TestClient(api)
        client.headers['Authorization'] = 'Bearer invalid_token_123'
        
        response = client.get("/api/auth/profile")
        assert response.status_code == 401
    
    def test_token_authentication_expired_token(self, api_client, user):
        """Тест аутентификации с просроченным токеном"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Создаем токен с истекшим сроком
        token = AuthToken.generate_token()
        auth_token = AuthToken.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        client = TestClient(api)
        client.headers['Authorization'] = f'Bearer {token}'
        
        response = client.get("/api/auth/profile")
        assert response.status_code == 401
    
    def test_token_authentication_inactive_token(self, api_client, user):
        """Тест аутентификации с неактивным токеном"""
        token = AuthToken.generate_token()
        auth_token = AuthToken.objects.create(
            user=user,
            token=token,
            is_active=False
        )
        
        client = TestClient(api)
        client.headers['Authorization'] = f'Bearer {token}'
        
        response = client.get("/api/auth/profile")
        assert response.status_code == 401
