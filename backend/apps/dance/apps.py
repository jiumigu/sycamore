from django.apps import AppConfig


class DanceConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.dance'
    label = 'dance'
    verbose_name = '舞蹈记录'
