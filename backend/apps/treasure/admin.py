from django.contrib import admin

from .models import GoodThing


@admin.register(GoodThing)
class GoodThingAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'rating', 'still_available', 'created_at')
    list_filter = ('category', 'still_available')
    search_fields = ('name', 'scene', 'why_good')
