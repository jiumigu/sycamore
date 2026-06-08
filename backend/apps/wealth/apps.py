from django.apps import AppConfig


class WealthConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.wealth'
    label = 'wealth'
    verbose_name = '财务管理'
