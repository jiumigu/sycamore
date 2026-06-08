from django.apps import AppConfig


class HealthConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.health'
    label = 'health'
    verbose_name = '健康管理'
