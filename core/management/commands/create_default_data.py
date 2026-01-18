from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Category, Tag

class Command(BaseCommand):
    help = 'Creates default data for the application'

    def handle(self, *args, **options):
        # Создание категорий
        categories = [
            'Technology',
            'Programming',
            'Design',
            'Business',
            'Personal',
        ]
        
        for cat_name in categories:
            Category.objects.get_or_create(name=cat_name)
            self.stdout.write(f'Created category: {cat_name}')
        
        # Создание тегов
        tags = [
            'python', 'django', 'javascript', 'react',
            'docker', 'aws', 'tutorial', 'beginners'
        ]
        
        for tag_name in tags:
            Tag.objects.get_or_create(name=tag_name)
            self.stdout.write(f'Created tag: {tag_name}')
        
        self.stdout.write(self.style.SUCCESS('Default data created successfully!'))
