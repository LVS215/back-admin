import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from ninja.testing import TestClient

from blog.urls import api
from core.models import Post, Category

class PostAPITests(TestCase):
    def setUp(self):
        self.client = TestClient(api.router)
        self.user = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="password123"
        )
        
        self.category = Category.objects.create(
            name="Technology",
            slug="technology"
        )
        
        # Создаем тестовый токен
        from core.models import AuthToken
        self.token = AuthToken.generate_token()
        self.auth_token = AuthToken.objects.create(
            user=self.user,
            token=self.token
        )
        
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    # Тест 1: Создание статьи (успешно)
    def test_create_post_success(self):
        post_data = {
            "title": "Test Post",
            "content": "This is a test post content.",
            "category_id": self.category.id,
            "status": "draft"
        }
        
        response = self.client.post(
            "/posts/", 
            json=post_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.count(), 1)
        
        post = Post.objects.first()
        self.assertEqual(post.title, "Test Post")
        self.assertEqual(post.author, self.user)
        self.assertEqual(post.category, self.category)
    
    # Тест 2: Создание статьи без авторизации
    def test_create_post_unauthorized(self):
        post_data = {
            "title": "Test Post",
            "content": "Content"
        }
        
        response = self.client.post("/posts/", json=post_data)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Post.objects.count(), 0)
    
    # Тест 3: Получение списка статей
    def test_list_posts(self):
        # Создаем несколько статей
        Post.objects.create(
            title="Post 1",
            content="Content 1",
            author=self.user,
            category=self.category,
            status="published"
        )
        Post.objects.create(
            title="Post 2",
            content="Content 2",
            author=self.user,
            category=self.category,
            status="published"
        )
        
        response = self.client.get("/posts/")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
    
    # Тест 4: Получение конкретной статьи
    def test_get_post(self):
        post = Post.objects.create(
            title="Test Post",
            content="Content",
            author=self.user,
            category=self.category,
            status="published"
        )
        
        response = self.client.get(f"/posts/{post.id}")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Test Post")
        self.assertEqual(response.json()["view_count"], 1)  # Счетчик должен увеличиться
    
    # Тест 5: Обновление статьи (автор)
    def test_update_post_author(self):
        post = Post.objects.create(
            title="Old Title",
            content="Old Content",
            author=self.user,
            category=self.category
        )
        
        update_data = {
            "title": "Updated Title",
            "content": "Updated Content"
        }
        
        response = self.client.put(
            f"/posts/{post.id}",
            json=update_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        
        post.refresh_from_db()
        self.assertEqual(post.title, "Updated Title")
        self.assertEqual(post.content, "Updated Content")
    
    # Тест 6: Обновление статьи (не автор)
    def test_update_post_not_author(self):
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="password123"
        )
        
        post = Post.objects.create(
            title="Test Post",
            content="Content",
            author=other_user,  # Другой автор!
            category=self.category
        )
        
        update_data = {
            "title": "Updated Title"
        }
        
        response = self.client.put(
            f"/posts/{post.id}",
            json=update_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)  # Post not found для этого автора
    
    # Тест 7: Удаление статьи (автор)
    def test_delete_post_author(self):
        post = Post.objects.create(
            title="Test Post",
            content="Content",
            author=self.user,
            category=self.category
        )
        
        response = self.client.delete(
            f"/posts/{post.id}",
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.count(), 0)
    
    # Тест 8: Удаление статьи (не автор)
    def test_delete_post_not_author(self):
        other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="password123"
        )
        
        post = Post.objects.create(
            title="Test Post",
            content="Content",
            author=other_user,
            category=self.category
        )
        
        response = self.client.delete(
            f"/posts/{post.id}",
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Post.objects.count(), 1)
