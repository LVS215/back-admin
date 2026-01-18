"""
Настройка админ-панели Django
Требование: Управление пользователями, статьями, комментариями, категориями
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from core.models import (
    UserProfile, 
    Category, 
    Post, 
    Comment, 
    AuthToken
)

# Inline для профиля пользователя
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ['bio', 'avatar', 'website']
    readonly_fields = ['avatar_preview']
    
    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%;" />',
                obj.avatar.url
            )
        return "-"
    avatar_preview.short_description = 'Avatar Preview'

# Кастомный UserAdmin
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'date_joined', 'is_staff', 'is_active', 'post_count', 'comment_count')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    inlines = (UserProfileInline,)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
       
