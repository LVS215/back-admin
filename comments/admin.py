# comments/admin.py
from django.contrib import admin
from .models import Comment

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('content_preview', 'article', 'author', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'created_at')
    search_fields = ('content', 'author__username', 'article__title')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('article', 'author', 'parent')
    actions = ['approve_comments', 'disapprove_comments']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
    
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} comments approved.")
    approve_comments.short_description = "Approve selected comments"
    
    def disapprove_comments(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(request, f"{queryset.count()} comments disapproved.")
    disapprove_comments.short_description = "Disapprove selected comments"