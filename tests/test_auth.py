import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from ninja.testing import TestClient

from blog.urls import api

class AuthAPITests(TestCase):
    def setUp(self):
        self.client = TestClient(api.router)
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "StrongPass123!"
        }
    
    # Тест 1: Успешная регистрация
    def test_register_success(self):
        response = self.client.post("/auth/register", json=self.user_data)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())
        self.assertIn("user", response.json())
        
        # Проверяем, что пользователь создан
        self.assertTrue(User.objects.filter(username="testuser").exists())
        
        # Проверяем длину токена (256 символов)
        token = response.json()["token"]
        self.assertEqual(len(token), 256)
    
    # Тест 2: Регистрация с существующим username
    def test_register_duplicate_username(self):
        # Создаем пользователя
        User.objects.create_user(
            username="testuser",
            email="existing@example.com",
            password="password123"
        )
        
        response = self.client.post("/auth/register", json=self.user_data)
        
        self.assertEqual(response.status_code, 401)  # AuthenticationError
        self.assertEqual(User.objects.filter(username="testuser").count(), 1)
    
    # Тест 3: Успешный вход
    def test_login_success(self):
        # Сначала регистрируем
        User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPass123!"
        )
        
        response = self.client.post("/auth/login", json={
            "username": "testuser",
            "password": "StrongPass123!"
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())
    
    # Тест 4: Неверные учетные данные
    def test_login_invalid_credentials(self):
        response = self.client.post("/auth/login", json={
            "username": "nonexistent",
            "password": "wrongpassword"
        })
        
        self.assertEqual(response.status_code, 401)
    
    # Тест 5: Получение текущего пользователя (с токеном)
    def test_get_current_user_with_token(self):
        # Создаем пользователя и токен
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        from core.models import AuthToken
        token = AuthToken.generate_token()
        auth_token = AuthToken.objects.create(user=user, token=token)
        
        # Делаем запрос с токеном
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "testuser")
    
    # Тест 6: Получение текущего пользователя без токена
    def test_get_current_user_unauthorized(self):
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)
