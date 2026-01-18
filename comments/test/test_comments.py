from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from users.models import User
from articles.models import Article, Category
from comments.models import Comment

class CommentAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.category = Category.objects.create(
            name='Technology',
            slug='technology'
        )
        
        self.article = Article.objects.create(
            title='Test Article',
            slug='test-article',
            content='Test content',
            author=self.user,
            category=self.category,
            status='published'
        )
        
        # Получаем токен
        response = self.client.post('/api/auth/token/pair/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.token = response.json()['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
    
    def test_create_comment(self):
        """Тест создания комментария"""
        data = {
            'content': 'This is a test comment'
        }
        
        response = self.client.post(f'/api/comments/article/{self.article.slug}/', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['content'], 'This is a test comment')
    
    def test_list_comments(self):
        """Тест получения списка комментариев"""
        # Создаем тестовые комментарии
        Comment.objects.create(
            article=self.article,
            author=self.user,
            content='First comment'
        )
        
        Comment.objects.create(
            article=self.article,
            author=self.user,
            content='Second comment'
        )
        
        response = self.client.get(f'/api/comments/article/{self.article.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
    
    def test_update_comment(self):
        """Тест обновления комментария"""
        comment = Comment.objects.create(
            article=self.article,
            author=self.user,
            content='Original comment'
        )
        
        data = {
            'content': 'Updated comment'
        }
        
        response = self.client.put(f'/api/comments/{comment.id}/', data, format='json')
        self.assertEqual(response.status_code, 200)
        
        comment.refresh_from_db()
        self.assertEqual(comment.content, 'Updated comment')
    
    def test_delete_comment(self):
        """Тест удаления комментария"""
        comment = Comment.objects.create(
            article=self.article,
            author=self.user,
            content='Comment to delete'
        )
        
        response = self.client.delete(f'/api/comments/{comment.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comment.objects.filter(id=comment.id).exists())