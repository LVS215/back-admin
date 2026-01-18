from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from users.models import User
from articles.models import Article, Category
import json

class ArticleAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            password='adminpass123',
            email='admin@example.com'
        )
        
        self.category = Category.objects.create(
            name='Technology',
            slug='technology',
            description='Tech related articles'
        )
        
        # Получаем токен для пользователя
        response = self.client.post('/api/auth/token/pair/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.token = response.json()['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
    
    def test_create_article(self):
        """Тест создания статьи"""
        data = {
            'title': 'Test Article',
            'slug': 'test-article',
            'content': 'This is a test article content',
            'excerpt': 'Test excerpt',
            'category_slug': 'technology',
            'status': 'published'
        }
        
        response = self.client.post('/api/articles/', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'Test Article')
        self.assertEqual(response.json()['slug'], 'test-article')
    
    def test_create_article_unauthorized(self):
        """Тест создания статьи без авторизации"""
        self.client.credentials()  # Убираем токен
        
        data = {
            'title': 'Test Article',
            'slug': 'test-article',
            'content': 'This is a test article content',
        }
        
        response = self.client.post('/api/articles/', data, format='json')
        self.assertEqual(response.status_code, 401)
    
    def test_list_articles(self):
        """Тест получения списка статей"""
        # Создаем тестовые статьи
        Article.objects.create(
            title='Article 1',
            slug='article-1',
            content='Content 1',
            author=self.user,
            category=self.category,
            status='published'
        )
        
        Article.objects.create(
            title='Article 2',
            slug='article-2',
            content='Content 2',
            author=self.user,
            category=self.category,
            status='draft'
        )
        
        response = self.client.get('/api/articles/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
    
    def test_get_article(self):
        """Тест получения конкретной статьи"""
        article = Article.objects.create(
            title='Test Article',
            slug='test-article',
            content='Test content',
            author=self.user,
            category=self.category,
            status='published'
        )
        
        response = self.client.get(f'/api/articles/{article.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'Test Article')
    
    def test_update_article(self):
        """Тест обновления статьи"""
        article = Article.objects.create(
            title='Original Title',
            slug='original-article',
            content='Original content',
            author=self.user,
            category=self.category,
            status='published'
        )
        
        data = {
            'title': 'Updated Title',
            'content': 'Updated content'
        }
        
        response = self.client.put(f'/api/articles/{article.slug}/', data, format='json')
        self.assertEqual(response.status_code, 200)
        
        article.refresh_from_db()
        self.assertEqual(article.title, 'Updated Title')
    
    def test_update_article_other_user(self):
        """Тест попытки обновления чужой статьи"""
        other_user = User.objects.create_user(
            username='otheruser',
            password='otherpass123'
        )
        
        article = Article.objects.create(
            title='Other User Article',
            slug='other-article',
            content='Other content',
            author=other_user,
            category=self.category,
            status='published'
        )
        
        data = {
            'title': 'Trying to update'
        }
        
        response = self.client.put(f'/api/articles/{article.slug}/', data, format='json')
        self.assertEqual(response.status_code, 403)
    
    def test_delete_article(self):
        """Тест удаления статьи"""
        article = Article.objects.create(
            title='To Delete',
            slug='to-delete',
            content='Delete me',
            author=self.user,
            category=self.category,
            status='published'
        )
        
        response = self.client.delete(f'/api/articles/{article.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Article.objects.filter(slug='to-delete').exists())
    
    def test_delete_article_other_user(self):
        """Тест попытки удаления чужой статьи"""
        other_user = User.objects.create_user(
            username='otheruser',
            password='otherpass123'
        )
        
        article = Article.objects.create(
            title='Other User Article',
            slug='other-user-article',
            content='Content',
            author=other_user,
            category=self.category,
            status='published'
        )
        
        response = self.client.delete(f'/api/articles/{article.slug}/')
        self.assertEqual(response.status_code, 403)