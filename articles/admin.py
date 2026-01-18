# articles/admin.py
from django.contrib import admin
from .models import Article, Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at', 'updated_at')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'author', 'category', 'status', 'published_at', 'created_at')
    list_filter = ('status', 'category', 'created_at', 'published_at')
    search_fields = ('title', 'content', 'excerpt')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at', 'published_at')
    raw_id_fields = ('author', 'category')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'content', 'excerpt')
        }),
        ('Relations', {
            'fields': ('author', 'category')
        }),
        ('Status', {
            'fields': ('status', 'published_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )