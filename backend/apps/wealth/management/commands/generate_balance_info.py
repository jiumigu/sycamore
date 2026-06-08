"""生成月度复盘数据管理命令"""
from datetime import datetime

from django.core.management.base import BaseCommand

from apps.wealth.services.review_service import generate_balance_info


class Command(BaseCommand):
    help = '从账单表聚合生成月度复盘数据'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='年份')
        parser.add_argument('--month', type=int, help='月份')
        parser.add_argument('--all-missing', action='store_true', help='批量生成所有缺失月份')
        parser.add_argument('--user_id', type=int, default=1, help='用户ID')

    def handle(self, *args, **options):
        user_id = options['user_id']

        if options['all_missing']:
            self._handle_all_missing(user_id)
        elif options['year'] and options['month']:
            obj = generate_balance_info(user_id, options['year'], options['month'])
            if obj:
                income_val = (obj.wageincome or 0) + (obj.otherincome or 0)
                expense_val = obj.outmoney or 0
                balance_val = obj.mbalance or 0
                self.stdout.write(self.style.SUCCESS(
                    f'已生成 {obj.yearmon} 复盘数据：收{income_val:.2f} 支{expense_val:.2f} 结余{balance_val:.2f}'
                ))
            else:
                self.stdout.write(self.style.WARNING('无对应月份记录'))
        else:
            self.print_help('manage.py', 'generate_balance_info')

    def _handle_all_missing(self, user_id: int):
        """查找有账单记录但缺少复盘数据的月份并批量生成"""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT year, month
                FROM wealth_bill_list
                WHERE user_id = %s
                ORDER BY year, month
            """, [user_id])
            bill_months = cursor.fetchall()

        from apps.wealth.models import WealthBalanceList
        count = 0
        for year, month in bill_months:
            yearmon = f"{year:04d}-{month:02d}"
            if not WealthBalanceList.objects.filter(yearmon=yearmon).exists():
                obj = generate_balance_info(user_id, year, month)
                self.stdout.write(f'  生成 {obj.yearmon}')
                count += 1

        self.stdout.write(self.style.SUCCESS(f'批量完成，共生成 {count} 条复盘记录'))
