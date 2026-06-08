from django.contrib import admin

from .models import DamsAccessLog, DamsFileResource


@admin.register(DamsFileResource)
class DamsFileResourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'file_category', 'file_size_mb', 'access_count', 'is_duplicate', 'is_organized']
    list_filter = ['file_category', 'is_duplicate', 'is_organized']
    search_fields = ['name', 'path']


@admin.register(DamsAccessLog)
class DamsAccessLogAdmin(admin.ModelAdmin):
    list_display = ['file', 'accessed_at']
    list_filter = ['accessed_at']
    date_hierarchy = 'accessed_at'
