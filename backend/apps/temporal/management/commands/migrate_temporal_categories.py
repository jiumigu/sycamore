"""历史数据迁移：把 TemporalTask 的去重 task_name(L3) 映射进 temporal_task_meta（L2 类型 / L1 归因）

设计（v0.2 §7 / v0.3 §3.6）：
- 不读取、不删除旧 category_level1/2/color 字段（只停止写入），历史数据零损失。
- 幂等：已存在的 task_name 跳过，重跑不产生重复。
- 命中 TASK_TO_L2 → 活动类型(L2)+默认归因(L1)；否则经 TASK_CATEGORY_MAPPING + LEGACY_FOUR_TO_L2；
  仍未命中 → 活动类型='未归类'、归因=None（留给用户在映射编辑器完善）。
- 不涉及「自建聚合分组」层（v3.57.0 已取消，group 字段保留空置）。

Usage:
    python manage.py migrate_temporal_categories
    python manage.py migrate_temporal_categories --dry-run
"""

from django.core.management.base import BaseCommand

from apps.temporal.constants import (
    LEGACY_FOUR_TO_L2,
    TASK_CATEGORY_MAPPING,
    TASK_TO_L2,
)
from apps.temporal.models import TaskMeta, TemporalTask


class Command(BaseCommand):
    help = '将 TemporalTask 的去重 task_name 迁移进 temporal_task_meta（L2 映射）'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际写入')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        # 注意：必须 order_by() 清空 Meta.ordering（-start_time），否则 Django 会把
        # start_time 注入 SELECT 列，DISTINCT 失效（2476 条虚增，真实仅 25 个）。
        names = list(
            TemporalTask.objects.order_by()
            .values_list('task_name', flat=True)
            .distinct()
        )
        self.stdout.write(f'外部表去重 task_name 数：{len(names)}')

        plan = []
        for tn in names:
            if TaskMeta.objects.filter(task_name=tn).exists():
                continue
            if tn in TASK_TO_L2:
                at, attr = TASK_TO_L2[tn]
            elif tn in TASK_CATEGORY_MAPPING:
                at, attr = LEGACY_FOUR_TO_L2[TASK_CATEGORY_MAPPING[tn]]
            else:
                at, attr = '未归类', None
            plan.append((tn, at, attr))

        self.stdout.write(f'待映射（不存在于 temporal_task_meta）：{len(plan)}')
        unclassified = sum(1 for _, at, _ in plan if at == '未归类')
        if unclassified:
            self.stdout.write(self.style.WARNING(
                f'其中 {unclassified} 个未命中映射，将落入「未归类」桶，请到映射编辑器完善'
            ))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN 模式，未实际写入'))
            for i, (tn, at, attr) in enumerate(plan[:10]):
                self.stdout.write(f'  #{i + 1} {tn} | {at} | {attr or "-"}')
            if len(plan) > 10:
                self.stdout.write(f'  … 其余 {len(plan) - 10} 条省略')
            return

        created = 0
        for tn, at, attr in plan:
            # get_or_create：DB 级幂等，避免并发/隔离下的重复插入
            _, is_new = TaskMeta.objects.get_or_create(
                task_name=tn,
                defaults={'activity_type': at, 'default_attribution': attr, 'is_system': False},
            )
            if is_new:
                created += 1
                if created % 200 == 0:
                    self.stdout.write(f'  已写入 {created} 条...')

        self.stdout.write(self.style.SUCCESS(
            f'迁移完成：新增 {created} 条 TaskMeta（未归类 {unclassified}），旧列未改动'
        ))
