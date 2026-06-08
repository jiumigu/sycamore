from django.db.models import Sum, Count
from django.core.management.base import BaseCommand

from apps.temporal.models import WeeklyTimeCache, TemporalTask
from datetime import date


class Command(BaseCommand):
    help = '刷新周度时间固化表'

    def handle(self, *args, **options):
        start_year = date.today().year - 5
        end_year = date.today().year + 5

        # 使用 TemporalTask 已有的 year/week 字段，每年 1 次查询聚合
        for year in range(start_year, end_year + 1):
            weekly_data = TemporalTask.objects.filter(
                year=year,
                week__isnull=False,
            ).values('week').annotate(
                total=Sum('duration_hours'),
                count=Count('id'),
            ).order_by('week')

            for item in weekly_data:
                week = item['week']
                total_hours = float(item['total'] or 0)
                task_count = item['count'] or 0

                WeeklyTimeCache.objects.update_or_create(
                    year=year, week=week,
                    defaults={
                        'total_hours': round(total_hours, 2),
                        'task_count': task_count,
                        'avg_hours_per_day': round(total_hours / 7, 2) if total_hours else 0,
                    },
                )

            self.stdout.write(f'  {year}: {len(weekly_data)} weeks cached')

        self.stdout.write(self.style.SUCCESS('周度缓存刷新完成'))
