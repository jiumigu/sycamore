from django.apps import AppConfig


class GoalsConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.goals'
    label = 'goals'
    verbose_name = '目标管理'
