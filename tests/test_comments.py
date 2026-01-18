import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from ninja.testing import TestClient

from blog.urls import api
from core.models import Post, Comment, Category

class CommentAPITests(TestCase):
    def setUp(self):
        self.client = TestClient(api.router)
        self.user = User.objects.create_user(
            username="commenter",
            email="commenter@example.com",
            password="password123"
        )
        
        self.category = Category.objects.create(
            name="Technology",
            slug="technology"
        )
        
        self.post = Post.objects.create(
            title="Test Post",
            content="Test Content",
            author=self.user,
            category=self.category,
            status="published"
        )
        
        # Создаем токен
        from core.models import AuthToken
        self.token = AuthToken.generate_token()
        self.auth_token = AuthToken.objects.create(
            user=self.user,
            token=self.token
        )
        
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    # Тест 1: Создание комментария (успешно)
    def test_create_comment_success(self):
        comment_data = {
            "content": "Great post!",
            "post_id": self.post.id
        }
        
        response = self.client.post(
            "/comments/",
            json=comment_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.count(), 1)
        
        comment = Comment.objects.first()
        self.assertEqual(comment.content, "Great post!")
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.post, self.post)
    
    # Тест 2: Создание комментария без авторизации
    def test_create_comment_unauthorized(self):
        comment_data = {
            "content": "Test comment",
            "post_id": self.post.id
        }
        
        response = self.client.post("/comments/", json=comment_data)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Comment.objects.count(), 0)
    
    # Тест 3: Получение списка комментариев
    def test_list_comments(self):
        # Создаем несколько комментариев
        Comment.objects.create(
            content="Comment 1",
            author=self.user,
            post=self.post
        )
        Comment.objects.create(
            content="Comment 2",
            author=self.user,
            post=self.post
        )
        
        response = self.client.get(f"/comments/?post_id={self.post.id}")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
    
    # Тест 4: Обновление комментария (автор)
    def test_update_comment_author(self):
        comment = Comment.objects.create(
            content="Old comment",
            author=self.user,
            post=self.post
        )
        
        update_data = {
            "content": "Updated comment"
        }
        
        response = self.client.put(
            f"/comments/{comment.id}",
            json=update_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        
        comment.refresh_from_db()
        self.assertEqual(comment.content, "Updated comment")
    
    # Тест 5: Обновление комментария (не автор)
    def test_update_comment_not_author(self):
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="password123"
        )
        
        comment = Comment.objects.create(
            content="Test comment",
            author=other_user,  # Другой автор!
            post=self.post
        )
        
        update_data = {
            "content": "Updated comment"
        }
        
        response = self.client.put(
            f"/comments/{comment.id}",
            json=update_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)
    
    # Тест 6: Удаление комментария (автор)
    def test_delete_comment_author(self):
        comment = Comment.objects.create(
            content="Test comment",
            author=self.user,
            post=self.post
        )
        
        response = self.client.delete(
            f"/comments/{comment.id}",
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.count(), 0)
    
    # Тест 7: Удаление комментария (не автор)
    def test_delete_comment_not_author(self):
        other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="password123"
        )
        
        comment = Comment.objects.create(
            content="Test comment",
            author=other_user,
            post=self.post
        )
        
        response = self.client.delete(
            f"/comments/{comment.id}",
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Comment.objects.count(), 1)
    
    # Тест 8: Создание вложенного комментария
    def test_create_nested_comment(self):
        parent_comment = Comment.objects.create(
            content="Parent comment",
            author=self.user,
            post=self.post
        )
        
        nested_data = {
            "content": "Reply to parent",
            "post_id": self.post.id,
            "parent_id": parent_comment.id
        }
        
        response = self.client.post(
            "/comments/",
            json=nested_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.count(), 2)
        
        nested_comment = Comment.objects.get(parent=parent_comment)
        self.assertEqual(nested_comment.content, "Reply to parent")
