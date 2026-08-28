"""将 reserve_items JSON 字段数据迁移到 wealth_fund_schedule_item 子表（幂等：已迁移的跳过）"""

from django.core.management.base import BaseCommand

from apps.wealth.models import FundSchedule, FundScheduleItem


class Command(BaseCommand):
    help = '将 FundSchedule.reserve_items JSON 数据迁移到独立子表 FundScheduleItem'

    def handle(self, *args, **options):
        created_count = 0
        schedule_count = 0
        skipped = 0

        schedules = FundSchedule.objects.all()
        for s in schedules:
            if s.items.exists():
                skipped += 1
                continue
            items = s.reserve_items or []
            if not items:
                continue
            FundScheduleItem.objects.bulk_create([
                FundScheduleItem(
                    schedule=s,
                    name=item.get('name', ''),
                    amount=item.get('amount', 0),
                    item_type=item.get('type', 'hard'),
                    linked_expense_id=item.get('linked_expense_id'),
                    sort_order=i,
                )
                for i, item in enumerate(items)
            ])
            created_count += len(items)
            schedule_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'迁移完成：{schedule_count} 条排程的 {created_count} 个预留项 → 子表（{skipped} 条已存在跳过）'
        ))
