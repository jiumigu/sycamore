from django.apps import AppConfig


class DamsConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.dams'
    label = 'dams'
    verbose_name = '数字资产管理'

    def ready(self):
        pass
