from django.contrib import admin

from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['bid', 'btitle', 'author', 'btype', 'status', 'recommend', 'reading_depth', 'readDate']
    list_filter = ['btype', 'status', 'years']
    search_fields = ['btitle', 'author', 'tags']
