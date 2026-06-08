"""初始化人生周历管理命令"""
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.wealth.services.calendar_init import init_week_calendar_for_user, update_lived_status


class Command(BaseCommand):
    help = '初始化人生周历（3172周）并更新已度过状态'

    def add_arguments(self, parser):
        parser.add_argument('--user_id', type=int, default=1, help='用户ID')
        default_birth = getattr(settings, 'WEALTH_BIRTH_DATE', '1995-01-01')
        parser.add_argument('--birth_date', type=str, default=default_birth, help='出生日期 YYYY-MM-DD')

    def handle(self, *args, **options):
        user_id = options['user_id']
        birth_date = date.fromisoformat(options['birth_date'])

        self.stdout.write(f'为用户 {user_id} 初始化周历，出生日期 {birth_date}...')
        created = init_week_calendar_for_user(user_id, birth_date)
        self.stdout.write(self.style.SUCCESS(f'创建 {created} 条周历记录'))

        updated = update_lived_status()
        self.stdout.write(self.style.SUCCESS(f'标记 {updated} 周为已度过'))
