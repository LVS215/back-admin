from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Category, Post, Comment

class Command(BaseCommand):
    """Создание тестовых данных"""
    
    def handle(self, *args, **options):
        # Создаем пользователей
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        
        author = User.objects.create_user(
            username='author',
            email='author@example.com',
            password='author123'
        )
        
        # Создаем категории
        categories = [
            ('Technology', 'technology'),
            ('Science', 'science'),
            ('Art', 'art'),
            ('Business', 'business'),
        ]
        
        for name, slug in categories:
            Category.objects.get_or_create(name=name, slug=slug)
            self.stdout.write(f'Created category: {name}')
        
        # Создаем статьи
        tech_category = Category.objects.get(slug='technology')
        
        posts = [
            {
                'title': 'Introduction to Django',
                'content': 'Django is a high-level Python web framework...',
                'author': author,
                'category': tech_category,
                'status': 'published',
            },
            {
                'title': 'REST API Best Practices',
                'content': 'Building REST APIs requires following certain best practices...',
                'author': author,
                'category': tech_category,
                'status': 'published',
            },
        ]
        
        for post_data in posts:
            post = Post.objects.create(**post_data)
            self.stdout.write(f'Created post: {post.title}')
            
            # Создаем комментарии
            comments = [
                {'content': 'Great article!', 'author': admin},
                {'content': 'Very helpful, thanks!', 'author': author},
            ]
            
            for comment_data in comments:
                Comment.objects.create(post=post, **comment_data)
        
        self.stdout.write(self.style.SUCCESS('Test data created successfully!'))
