"""迁移旧数据库 l_dance_list 到 hobby_dance_list

Usage:
    python manage.py migrate_dance
    python manage.py migrate_dance --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import connection

from apps.dance.constants import DANCE_TYPE_ICONS
from apps.dance.models import DanceRecord


class Command(BaseCommand):
    help = '迁移 sycamore_db.l_dance_list 到 hobby_dance_list'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际写入')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM sycamore_db.l_dance_list")
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        self.stdout.write(f'旧表记录数：{len(rows)}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN 模式，未实际写入'))
            for i, row in enumerate(rows[:5]):
                data = dict(zip(columns, row))
                self.stdout.write(
                    f'  #{i + 1} {data["study_time"]} | {data["dance_type"]} | '
                    f'{data["difficulty"]} | {data["teacher_name"]} | 评分:{data["score"]}'
                )
            return

        created = 0
        batch = []
        for row in rows:
            data = dict(zip(columns, row))
            st = data['study_time']
            if not st:
                continue

            batch.append(DanceRecord(
                study_time=st,
                score=data['score'] or 1,
                teacher_name=data.get('teacher_name') or '',
                dance_type=data.get('dance_type', 'jazz'),
                difficulty=data.get('difficulty', '入门'),
                weekinfo=['周一', '周二', '周三', '周四', '周五', '周六', '周日'][st.weekday()],
                remark=data.get('remark') or '',
                file_path=data.get('file_path') or '',
                year=st.year,
                month=st.month,
                quarter=(st.month - 1) // 3 + 1,
                duration_minutes=60,
                energy_level=None,
                improvement_note='',
            ))

            if len(batch) >= 200:
                DanceRecord.objects.bulk_create(batch)
                created += len(batch)
                self.stdout.write(f'  已写入 {created} 条...')
                batch = []

        if batch:
            DanceRecord.objects.bulk_create(batch)
            created += len(batch)

        self.stdout.write(self.style.SUCCESS(f'迁移完成：共写入 {created} 条记录'))
