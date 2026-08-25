from django.contrib import admin

from .models import LifeSample, ObsidianConfig


@admin.register(LifeSample)
class LifeSampleAdmin(admin.ModelAdmin):
    list_display = ['name', 'sample_type', 'summary', 'obsidian_path', 'created_at']
    list_filter = ['sample_type']
    search_fields = ['name', 'alias']


@admin.register(ObsidianConfig)
class ObsidianConfigAdmin(admin.ModelAdmin):
    list_display = ['enabled', 'vault_path', 'samples_folder']
