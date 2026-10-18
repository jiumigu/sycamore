from django.apps import AppConfig


class SelfRunConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.selfrun'
    label = 'selfrun'
    verbose_name = '自我运转'
