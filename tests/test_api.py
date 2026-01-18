from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from ninja.testing import TestClient

from core.models import Article, Comment, Category
from blog.urls import api

User = get_user_model()

class AuthAPITestCase(TestCase):
    def setUp(self):
        self.client = TestClient(api)
        self.user_data = {
            "username": "testuser",
            "password": "testpass123",
            "email": "test@example.com"
        }

    def test_register_success(self):
        response = self.client.post("/api/auth/register", json=self.user_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())
        self.assertIn("user", response.json())

    def test_register_duplicate_username(self):
        # Первая регистрация
        self.client.post("/api/auth/register", json=self.user_data)
        # Вторая регистрация с тем же username
        response = self.client.post("/api/auth/register", json=self.user_data)
        self.assertEqual(response.status_code, 400)

    def test_login_success(self):
        # Сначала регистрируем пользователя
        self.client.post("/api/auth/register", json=self.user_data)
        # Логинимся
        response = self.client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "testpass123"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())

    def test_login_invalid_credentials(self):
        response = self.client.post("/api/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        self.assertEqual(response.status_code, 401)

class ArticleAPITestCase(TestCase):
    def setUp(self):
        self.client = TestClient(api)
        # Создаем пользователя и получаем токен
        user_response = self.client.post("/api/auth/register", json={
            "username": "author",
            "password": "authorpass123"
        })
        self.token = user_response.json()["token"]
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
        
        # Создаем категорию
        self.category = Category.objects.create(
            name="Technology",
            slug="technology"
        )

    def test_create_article_success(self):
        data = {
            "title": "Test Article",
            "content": "This is a test article content.",
            "category_id": self.category.id,
            "is_published": True
        }
        response = self.client.post("/api/articles/", 
                                  json=data, 
                                  headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Test Article")

    def test_create_article_unauthorized(self):
        data = {
            "title": "Test Article",
            "content": "This is a test article content.",
        }
        response = self.client.post("/api/articles/", json=data)
        self.assertEqual(response.status_code, 401)

    def test_list_articles(self):
        # Создаем статью
        user = User.objects.get(username="author")
        Article.objects.create(
            title="Test Article",
            content="Content",
            author=user,
            category=self.category
        )
        
        response = self.client.get("/api/articles/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_update_article_success(self):
        # Создаем статью
        user = User.objects.get(username="author")
        article = Article.objects.create(
            title="Original Title",
            content="Original Content",
            author=user
        )
        
        data = {"title": "Updated Title"}
        response = self.client.put(f"/api/articles/{article.id}", 
                                 json=data,
                                 headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Updated Title")

    def test_update_article_unauthorized(self):
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            username="other",
            password="otherpass123"
        )
        # Создаем статью от другого пользователя
        article = Article.objects.create(
            title="Other Article",
            content="Content",
            author=other_user
        )
        
        data = {"title": "Try to Update"}
        response = self.client.put(f"/api/articles/{article.id}", 
                                 json=data,
                                 headers=self.auth_headers)
        self.assertEqual(response.status_code, 403)

    def test_delete_article_success(self):
        user = User.objects.get(username="author")
        article = Article.objects.create(
            title="To Delete",
            content="Content",
            author=user
        )
        
        response = self.client.delete(f"/api/articles/{article.id}", 
                                    headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Article.objects.filter(id=article.id).exists())

class CommentAPITestCase(TestCase):
    def setUp(self):
        self.client = TestClient(api)
        # Создаем пользователя
        user_response = self.client.post("/api/auth/register", json={
            "username": "commenter",
            "password": "commentpass123"
        })
        self.token = user_response.json()["token"]
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
        
        # Создаем статью
        self.user = User.objects.get(username="commenter")
        self.article = Article.objects.create(
            title="Test Article",
            content="Content",
            author=self.user
        )

    def test_create_comment_success(self):
        data = {
            "article_id": self.article.id,
            "content": "Great article!"
        }
        response = self.client.post("/api/comments/", 
                                  json=data, 
                                  headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "Great article!")

    def test_list_comments(self):
        # Создаем комментарий
        Comment.objects.create(
            article=self.article,
            author=self.user,
            content="Test comment"
        )
        
        response = self.client.get(f"/api/comments/article/{self.article.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_update_comment_success(self):
        # Создаем комментарий
        comment = Comment.objects.create(
            article=self.article,
            author=self.user,
            content="Original comment"
        )
        
        data = {"content": "Updated comment"}
        response = self.client.put(f"/api/comments/{comment.id}", 
                                 json=data,
                                 headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "Updated comment")

    def test_update_comment_unauthorized(self):
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            username="other",
            password="otherpass123"
        )
        # Создаем комментарий от другого пользователя
        comment = Comment.objects.create(
            article=self.article,
            author=other_user,
            content="Other comment"
        )
        
        data = {"content": "Try to update"}
        response = self.client.put(f"/api/comments/{comment.id}", 
                                 json=data,
                                 headers=self.auth_headers)
        self.assertEqual(response.status_code, 403)
