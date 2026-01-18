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
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    readonly_fields = ('last_login', 'date_joined')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _post_count=Count('posts'),
            _comment_count=Count('comments')
        )
        return queryset
    
    def post_count(self, obj):
        return obj._post_count
    post_count.admin_order_field = '_post_count'
    post_count.short_description = 'Posts'
    
    def comment_count(self, obj):
        return obj._comment_count
    comment_count.admin_order_field = '_comment_count'
    comment_count.short_description = 'Comments'

# Category Admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'post_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(_post_count=Count('posts'))
        return queryset
    
    def post_count(self, obj):
        return obj._post_count
    post_count.admin_order_field = '_post_count'
    post_count.short_description = 'Posts'

# Post Admin
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'status', 'published_at', 'view_count', 'like_count', 'created_at')
    list_filter = ('status', 'category', 'published_at', 'created_at')
    search_fields = ('title', 'content', 'excerpt', 'author__username')
    readonly_fields = ('slug', 'view_count', 'like_count', 'created_at', 'updated_at', 'published_at')
    raw_id_fields = ('author', 'category', 'created_by', 'updated_by')
    date_hierarchy = 'published_at'
    list_per_page = 20
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'content', 'excerpt')
        }),
        ('Relations', {
            'fields': ('author', 'category')
        }),
        ('Status', {
            'fields': ('status', 'published_at'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('view_count', 'like_count'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['publish_selected', 'archive_selected', 'reset_view_count']
    
    def publish_selected(self, request, queryset):
        updated = queryset.update(
            status=Post.STATUS_PUBLISHED,
            published_at=timezone.now()
        )
        self.message_user(request, f"{updated} posts published successfully.")
    publish_selected.short_description = "Publish selected posts"
    
    def archive_selected(self, request, queryset):
        updated = queryset.update(status=Post.STATUS_ARCHIVED)
        self.message_user(request, f"{updated} posts archived successfully.")
    archive_selected.short_description = "Archive selected posts"
    
    def reset_view_count(self, request, queryset):
        updated = queryset.update(view_count=0)
        self.message_user(request, f"View count reset for {updated} posts.")
    reset_view_count.short_description = "Reset view count for selected posts"
    
    def save_model(self, request, obj, form, change):
        if not change:  # При создании
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

# Comment Admin
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('content_preview', 'author', 'post_link', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'created_at', 'post')
    search_fields = ('content', 'author__username', 'post__title')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('author', 'post', 'parent', 'created_by', 'updated_by')
    list_per_page = 50
    
    fieldsets = (
        ('Content', {
            'fields': ('content', 'post', 'parent')
        }),
        ('Author', {
            'fields': ('author', 'is_approved')
        }),
        ('Audit', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_selected', 'disapprove_selected']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'
    
    def post_link(self, obj):
        url = reverse('admin:core_post_change', args=[obj.post.id])
        return format_html('<a href="{}">{}</a>', url, obj.post.title)
    post_link.short_description = 'Post'
    post_link.admin_order_field = 'post__title'
    
    def approve_selected(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} comments approved.")
    approve_selected.short_description = "Approve selected comments"
    
    def disapprove_selected(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f"{updated} comments disapproved.")
    disapprove_selected.short_description = "Disapprove selected comments"
    
    def save_model(self, request, obj, form, change):
        if not change:  # При создании
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

# AuthToken Admin
@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token_preview', 'name', 'is_active', 'last_used', 'expires_at', 'created_at')
    list_filter = ('is_active', 'created_at', 'expires_at')
    search_fields = ('user__username', 'name', 'token')
    readonly_fields = ('token', 'token_hash', 'created_at', 'updated_at', 'last_used')
    raw_id_fields = ('user',)
    
    fieldsets = (
        ('Token Information', {
            'fields': ('token', 'token_hash', 'name', 'user')
        }),
        ('Status', {
            'fields': ('is_active', 'expires_at', 'last_used')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['deactivate_selected', 'extend_expiry']
    
    def token_preview(self, obj):
        if obj.token:
            return f"{obj.token[:20]}..."
        return "-"
    token_preview.short_description = 'Token'
    
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} tokens deactivated.")
    deactivate_selected.short_description = "Deactivate selected tokens"
    
    def extend_expiry(self, request, queryset):
        from django.utils import timezone
        new_expiry = timezone.now() + timezone.timedelta(days=30)
        updated = queryset.update(expires_at=new_expiry)
        self.message_user(request, f"Expiry extended for {updated} tokens.")
    extend_expiry.short_description = "Extend expiry by 30 days"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

# Перерегистрируем User модель с кастомным UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Настройка админ-сайта
admin.site.site_header = "Blog Platform Administration"
admin.site.site_title = "Blog Platform Admin"
admin.site.index_title = "Welcome to Blog Platform Administration"
