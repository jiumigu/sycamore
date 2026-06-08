from django.apps import AppConfig


class InboxConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'apps.inbox'
    label = 'inbox'
    verbose_name = '收件箱'
