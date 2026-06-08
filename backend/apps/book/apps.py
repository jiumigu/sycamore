from django.apps import AppConfig


class BookConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.book'
    label = 'book'
    verbose_name = '书籍阅读'
