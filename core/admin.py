from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Article, Comment, Category

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'date_joined')
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Token', {'fields': ('token',)}),
    )

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'created_at', 'is_published')
    list_filter = ('is_published', 'category', 'created_at')
    search_fields = ('title', 'content', 'author__username')
    raw_id_fields = ('author',)
    date_hierarchy = 'created_at'

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'article', 'created_at', 'parent')
    list_filter = ('created_at', 'article')
    search_fields = ('content', 'author__username', 'article__title')
    raw_id_fields = ('author', 'article', 'parent')
