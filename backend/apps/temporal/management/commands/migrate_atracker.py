"""迁移旧数据库 o_atracker_tasks_list 到 temporal_time_atracker_tasks_list

v3.58.5 起与 CSV 导入口径对齐：**按原始记录逐条迁移**（不再按「任务名 + 日期」合并），
去重键 = (task_name, start_time)，重复执行幂等。

Usage:
    python manage.py migrate_atracker
    python manage.py migrate_atracker --dry-run
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from apps.temporal.models import TemporalTask
from apps.temporal.services import _ensure_task_meta


class Command(BaseCommand):
    help = '迁移 sycamore_db.o_atracker_tasks_list 到 temporal_time_atracker_tasks_list（逐条）'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际写入')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # 读取旧表数据
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM sycamore_db.o_atracker_tasks_list")
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        self.stdout.write(f'旧表记录数：{len(rows)}')

        # 去重键 = (task_name, start_time)：同一条原始记录重复出现时只迁一次
        deduped: dict[tuple[str, object], dict] = {}
        duplicated = 0
        for data in rows:
            name = (data.get('task_name') or '').strip()
            start = data.get('start_time')
            if not name or not start:
                continue
            key = (name, start)
            if key in deduped:
                duplicated += 1
                continue
            deduped[key] = data

        self.stdout.write(f'去重后记录数：{len(deduped)}（旧表内重复 {duplicated} 条）')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN 模式，未实际写入'))
            preview = sorted(deduped.items(), key=lambda kv: kv[0][1])[:5]
            for i, ((name, start), data) in enumerate(preview):
                self.stdout.write(f'  #{i + 1} {name} | {start} | {data.get("duration_hours")}h')
            self.stdout.write(self.style.WARNING(f'共 {len(deduped)} 条待迁移'))
            return

        created = updated = skipped = 0
        with transaction.atomic():
            for (name, start), data in deduped.items():
                # 旧库 start_time 为本地 naive 时间 → 统一 make_aware，与 CSV 导入口径一致
                start_aware = timezone.make_aware(start) if timezone.is_naive(start) else start
                end_raw = data.get('end_time')
                end_aware = None
                if end_raw is not None:
                    end_aware = timezone.make_aware(end_raw) if timezone.is_naive(end_raw) else end_raw
                hours = float(data.get('duration_hours') or 0)
                d = start_aware.date()

                existing = TemporalTask.objects.filter(
                    task_name=name,
                    start_time__gte=start_aware,
                    start_time__lt=start_aware + timedelta(seconds=1),
                ).first()

                if existing:
                    if abs(float(existing.duration_hours or 0) - hours) < 0.01:
                        skipped += 1
                        continue
                    TemporalTask.objects.filter(id=existing.id).update(
                        duration_hours=hours,
                        end_time=end_aware or existing.end_time,
                        notes=data.get('notes') or existing.notes,
                        updated_at=timezone.now(),
                    )
                    updated += 1
                else:
                    TemporalTask.objects.create(
                        task_name=name,
                        task_description=data.get('task_description') or '',
                        start_time=start_aware,
                        end_time=end_aware,
                        duration_hours=hours,
                        notes=data.get('notes') or '',
                        tags=data.get('tags') or '',
                        task_type=name,
                        year=d.year,
                        mon=f'{d.month:02d}',
                        day=d.day,
                        week=d.isocalendar()[1],
                        quarter=(d.month - 1) // 3 + 1,
                    )
                    created += 1

                if (created + updated) % 500 == 0:
                    self.stdout.write(f'  已处理 {created + updated} 条...')

        # 为新出现的 task_name 建 L2 映射（命中 TASK_TO_L2 带类型+归因，否则进未归类桶）
        _ensure_task_meta(sorted({name for name, _ in deduped}))

        self.stdout.write(self.style.SUCCESS(
            f'迁移完成：新增 {created} 条、更新 {updated} 条、跳过 {skipped} 条'
            f'（去重后共 {len(deduped)} 条）'
        ))
