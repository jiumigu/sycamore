from django.contrib import admin

from .models import ShowroomCase, ShowroomProfile, ShowroomSkill, ShowroomWork


@admin.register(ShowroomProfile)
class ShowroomProfileAdmin(admin.ModelAdmin):
    list_display = ('ip_name', 'tagline', 'updated_at')


@admin.register(ShowroomCase)
class ShowroomCaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'is_visible', 'sort_order')
    list_filter = ('is_visible',)
    search_fields = ('title', 'client')


@admin.register(ShowroomSkill)
class ShowroomSkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'is_visible', 'sort_order')
    list_filter = ('level', 'is_visible')


@admin.register(ShowroomWork)
class ShowroomWorkAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'is_visible', 'sort_order')
    list_filter = ('is_visible',)
