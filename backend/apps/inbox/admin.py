from django.contrib import admin

from .models import InboxItem, InboxProcessLog


@admin.register(InboxItem)
class InboxItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'content', 'category', 'priority', 'status', 'due_date', 'created_at']
    list_filter = ['category', 'priority', 'status', 'source']
    search_fields = ['content', 'description', 'tags']
    ordering = ['-created_at']


@admin.register(InboxProcessLog)
class InboxProcessLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'inbox', 'action', 'target_type', 'target_id', 'created_at']
    list_filter = ['action']
