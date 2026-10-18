from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from apps.temporal.models import TemporalTask, WeeklyTimeCache


class Command(BaseCommand):
    help = '刷新周度时间固化表'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只报告将要写入 / 清理的周，不落库',
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run'))

        # ⚠️ 年份范围**由数据决定**，不再用「今年 ± 5」这类滚动窗口。
        #    滚动下界有两个静默面：
        #      ① 最早那几年会被挡在窗口外，永远进不来（2026 年跑 ⇒ 2020 的 190 条 / 40 周进不去）；
        #      ② 窗口逐年上移后，出窗的年份不再重算，而本命令又从不删行
        #         ⇒ 旧值留在固化表里**冒充现状**（「有值但陈旧」比「缺失」更难发现）。
        #    改成「源表有的年份 ∪ 固化表已有的年份」：
        #      前者保证一条不漏，后者保证源表被清空的年份也会被走到（从而清掉残留行）。
        source_years = set(
            TemporalTask.objects
            .filter(year__isnull=False, week__isnull=False)
            .values_list('year', flat=True)
            .distinct()
        )
        cache_years = set(
            WeeklyTimeCache.objects.values_list('year', flat=True).distinct()
        )
        years = sorted(source_years | cache_years)

        total_weeks = 0
        total_pruned = 0

        for year in years:
            # 使用 TemporalTask 已有的 year/week 字段，每年 1 次查询聚合
            weekly_data = TemporalTask.objects.filter(
                year=year,
                week__isnull=False,
            ).values('week').annotate(
                total=Sum('duration_hours'),
                count=Count('id'),
            ).order_by('week')

            weeks = []
            for item in weekly_data:
                week = item['week']
                total_hours = float(item['total'] or 0)
                task_count = item['count'] or 0

                if not dry_run:
                    WeeklyTimeCache.objects.update_or_create(
                        year=year, week=week,
                        defaults={
                            'total_hours': round(total_hours, 2),
                            'task_count': task_count,
                            'avg_hours_per_day': round(total_hours / 7, 2) if total_hours else 0,
                        },
                    )
                weeks.append(week)

            # 源表已经没有的周 ⇒ 固化表的对应行必须跟着消失，否则就是「有值但陈旧」
            stale = WeeklyTimeCache.objects.filter(year=year)
            if weeks:
                stale = stale.exclude(week__in=weeks)
            pruned = stale.count()
            if pruned and not dry_run:
                stale.delete()

            total_weeks += len(weeks)
            total_pruned += pruned

            note = f' / 清理陈旧 {pruned} 周' if pruned else ''
            self.stdout.write(f'  {year}: {len(weeks)} weeks cached{note}')

        prefix = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}周度缓存刷新完成：{len(years)} 个年份 · {total_weeks} 周'
            + (f' · 清理陈旧 {total_pruned} 周' if total_pruned else '')
        ))
