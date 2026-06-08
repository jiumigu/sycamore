"""迁移旧数据库 sycamore_db.o_health_info 到 health_step_info

Usage:
    python manage.py migrate_health
    python manage.py migrate_health --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import connection

from apps.health.models import HealthRecord


# 旧数据中 htype=5（桌下神器/综合步数）映射到新系统 htype=1（步数）
HTYPE_MAP = {1: 1, 4: 4, 5: 1}


class Command(BaseCommand):
    help = '迁移 sycamore_db.o_health_info 到 health_step_info'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际写入')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM sycamore_db.o_health_info")
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        self.stdout.write(f'旧表记录数：{len(rows)}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN 模式，未实际写入'))
            for i, row in enumerate(rows[:5]):
                data = dict(zip(columns, row))
                new_htype = HTYPE_MAP.get(data['htype'], data['htype'])
                self.stdout.write(
                    f'  #{i + 1} hid={data["hid"]} time={data["time"]} '
                    f'htype={data["htype"]}→{new_htype} '
                    f'steps={data["steps"]} total={data["total"]} '
                    f'remark={data["remark"] or ""}'
                )

            # 统计类型分布
            htype_counts = {}
            for row in rows:
                data = dict(zip(columns, row))
                old = data['htype']
                new = HTYPE_MAP.get(old, old)
                htype_counts[f'{old}→{new}'] = htype_counts.get(f'{old}→{new}', 0) + 1
            self.stdout.write('\n类型映射：')
            for k, v in sorted(htype_counts.items()):
                self.stdout.write(f'  htype {k}: {v} 条')
            return

        created = 0
        skipped = 0
        batch = []
        for row in rows:
            data = dict(zip(columns, row))

            old_htype = data['htype']
            new_htype = HTYPE_MAP.get(old_htype)
            if new_htype is None:
                self.stdout.write(self.style.WARNING(f'  跳过未知 htype={old_htype} (hid={data["hid"]})'))
                skipped += 1
                continue

            batch.append(HealthRecord(
                steps=data['steps'],
                htype=new_htype,
                cofficient=data['cofficient'],
                total=data['total'],
                time=data['time'],
                remark=(data['remark'] or '').strip() or None,
                years=data['years'],
                user_id=None,
            ))

            if len(batch) >= 200:
                HealthRecord.objects.bulk_create(batch)
                created += len(batch)
                self.stdout.write(f'  已写入 {created} 条...')
                batch = []

        if batch:
            HealthRecord.objects.bulk_create(batch)
            created += len(batch)

        self.stdout.write(self.style.SUCCESS(
            f'迁移完成：共写入 {created} 条'
            + (f'，跳过 {skipped} 条' if skipped else '')
        ))
