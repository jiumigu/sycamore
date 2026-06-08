"""迁移旧数据库 o_atracker_tasks_list 到 temporal_time_atracker_tasks_list

Usage:
    python manage.py migrate_atracker
    python manage.py migrate_atracker --dry-run
"""

from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from apps.temporal.constants import CATEGORY_COLORS, TASK_CATEGORY_MAPPING
from apps.temporal.models import TemporalTask


class Command(BaseCommand):
    help = '迁移 sycamore_db.o_atracker_tasks_list 到 temporal_time_atracker_tasks_list'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际写入')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # 读取旧表数据
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM sycamore_db.o_atracker_tasks_list")
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        self.stdout.write(f'旧表记录数：{len(rows)}')

        # 按 (task_name, date) 分组去重
        grouped = defaultdict(lambda: {'duration_hours': 0.0, 'first': None})
        for row in rows:
            data = dict(zip(columns, row))
            name = (data.get('task_name') or '').strip()
            start = data.get('start_time')
            if not name or not start:
                continue
            d = start.date()
            key = (name, d)
            grouped[key]['duration_hours'] += float(data.get('duration_hours') or 0)
            if grouped[key]['first'] is None:
                grouped[key]['first'] = data

        self.stdout.write(f'去重后记录数：{len(grouped)}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN 模式，未实际写入'))
            # 输出前 5 条预览
            for i, (key, g) in enumerate(sorted(grouped.items())[:5]):
                name, d = key
                f = g['first']
                category = TASK_CATEGORY_MAPPING.get(name, '维护与秩序')
                self.stdout.write(
                    f'  #{i + 1} {name} | {d} | {g["duration_hours"]:.2f}h | {category}'
                )
            self.stdout.write(self.style.WARNING(f'共 {len(grouped)} 条待迁移'))
            return

        # 批量写入
        created = 0
        batch = []
        for (name, d), g in grouped.items():
            f = g['first']
            category = TASK_CATEGORY_MAPPING.get(name, '维护与秩序')
            color = CATEGORY_COLORS.get(category, '#9CA3AF')

            batch.append(TemporalTask(
                task_name=name,
                task_description=f.get('task_description') or '',
                start_time=f.get('start_time'),
                end_time=f.get('end_time'),
                duration=f.get('duration'),
                duration_hours=round(g['duration_hours'], 4),
                notes=f.get('notes') or '',
                tags=f.get('tags') or '',
                task_type=name,
                year=d.year,
                mon=f'{d.month:02d}',
                day=d.day,
                week=d.isocalendar()[1],
                quarter=(d.month - 1) // 3 + 1,
                category_level1=category,
                category_color=color,
            ))

            if len(batch) >= 500:
                TemporalTask.objects.bulk_create(batch)
                created += len(batch)
                self.stdout.write(f'  已写入 {created} 条...')
                batch = []

        if batch:
            TemporalTask.objects.bulk_create(batch)
            created += len(batch)

        self.stdout.write(self.style.SUCCESS(f'迁移完成：共写入 {created} 条记录'))
