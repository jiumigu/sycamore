from django.apps import AppConfig


class RelationConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.relation'
    label = 'relation'
    verbose_name = '关系管理'

    def ready(self):
        import apps.relation.signals  # noqa: F401
