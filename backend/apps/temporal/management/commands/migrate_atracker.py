"""迁移旧数据库 o_atracker_tasks_list 到 temporal_time_atracker_tasks_list

v3.58.5 起与 CSV 导入口径对齐：**按原始记录逐条迁移**（不再按「任务名 + 日期」合并）。

判重（v3.60.29 起）= **同任务名 + 时段重叠**，走 `services.find_duplicate_task`，
与 CSV 导入**共用一份实现**。⚠️ 旧口径 `(task_name, start_time)` 精确相等会被
`import_worklog` 规则 A 的「时段补全」（改写 start_time 08:05→08:00）打穿 ⇒
重跑本命令时**静默多迁一条**（2026-09-17 就是这么多了 9.92h 一条，TECH-NOTES §64）。

Usage:
    python manage.py migrate_atracker
    python manage.py migrate_atracker --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from apps.temporal.models import TemporalTask
from apps.temporal.services import _ensure_task_meta, find_duplicate_task

# 来源标记（v3.64.34 补）：本命令此前**完全不写** `import_batch`，重跑一次就会
# 往「未标注」桶里灌一批记录，且事后无从区分。裸词与 `timer` / `worklog` 同风格，
# 由 `constants.SOURCE_BATCH_EXACT` 认成「旧库迁移」。
ATRACKER_BATCH = 'atracker'


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

        # 【源数据内】去重键 = (task_name, start_time)：同一条原始记录在旧表里重复出现时只迁一次。
        # ⚠️ 这与「库里是否已有这条记录」是**两回事** —— 后者见下方 find_duplicate_task。
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

        created = updated = skipped = protected = 0
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

                # 判重 = 「同任务名 + 时段重叠」（与 CSV 导入共用单一真源 `find_duplicate_task`）。
                # 旧的秒级精确匹配会被 import_worklog 的「时段补全」改写 start_time 打穿。
                existing = find_duplicate_task(name, start_aware, end_aware, hours)

                if existing:
                    # 🔴 v3.60.29 保护（与 CSV 导入同口径）：命中但**开始时刻不同** ⇒
                    # 库里这条的起止被 `import_worklog` 的「时段补全」改写过，源数据带的是
                    # 改写之前的旧值 ⇒ 不许覆盖回去（否则每次重跑本命令都会**静默撤销**
                    # 那次日志校准）。旧判重命中不了这条，是直接 create 出一条重复。
                    if (existing.start_time.replace(microsecond=0)
                            != start_aware.replace(microsecond=0)):
                        protected += 1
                        continue
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
                        # 新迁进来的记录自报家门；**更新已有记录时不动**它的来源
                        import_batch=ATRACKER_BATCH,
                    )
                    created += 1

                if (created + updated) % 500 == 0:
                    self.stdout.write(f'  已处理 {created + updated} 条...')

        # 为新出现的 task_name 建 L2 映射（命中 TASK_TO_L2 带类型+归因，否则进未归类桶）
        _ensure_task_meta(sorted({name for name, _ in deduped}))

        self.stdout.write(self.style.SUCCESS(
            f'迁移完成：新增 {created} 条、更新 {updated} 条、跳过 {skipped} 条、'
            f'保留校准值 {protected} 条（去重后共 {len(deduped)} 条）'
        ))
