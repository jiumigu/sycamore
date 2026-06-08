from django.apps import AppConfig


class SugarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sugar'
    label = 'sugar'
    verbose_name = '小确幸'
