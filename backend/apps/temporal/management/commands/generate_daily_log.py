"""每天凌晨自动生成默认日记的管理命令"""
from django.core.management.base import BaseCommand

from apps.temporal.services import DailyLogAutoService


class Command(BaseCommand):
    help = '为今天生成默认日记（如果今天还没有）'

    def handle(self, *args, **options):
        log = DailyLogAutoService.generate_default_log()
        if log:
            self.stdout.write(self.style.SUCCESS(f'已生成默认日记：{log.begin_date}'))
        else:
            self.stdout.write('今天已有日记，跳过')
