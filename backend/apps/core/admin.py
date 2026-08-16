from django.contrib import admin

from .models import SystemPreset, UserProfile


@admin.register(SystemPreset)
class SystemPresetAdmin(admin.ModelAdmin):
    list_display = ('preset_type', 'values', 'updated_at')
    search_fields = ('preset_type',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'privacy_mode', 'logseq_path')
