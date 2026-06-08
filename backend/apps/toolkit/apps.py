from django.apps import AppConfig


class ToolkitConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.toolkit'
    label = 'toolkit'
    verbose_name = '工具集'

    def ready(self):
        from apps.toolkit.registry import ToolRegistry
        ToolRegistry.auto_discover()
