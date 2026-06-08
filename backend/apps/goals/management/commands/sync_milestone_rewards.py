"""同步历史已完成里程碑的奖励

两步操作：
  1. 升级旧数据：对有 reward_value 但未启用奖励的目标启用奖励
  2. 补发奖励：为 status='completed' 但 reward_synced=False 的里程碑发放奖励

Usage:
    python manage.py sync_milestone_rewards
    python manage.py sync_milestone_rewards --dry-run  # 仅预览，不实际发放
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.goals.models import Goal, Milestone
from apps.goals.services import MilestoneRewardService


class Command(BaseCommand):
    help = '为历史已完成里程碑补发奖励'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际发放')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # ── 第一步：升级旧数据 ──
        self.stdout.write(self.style.WARNING('=== 第一步：升级目标奖励设置 ==='))
        upgraded_goals = Goal.objects.filter(
            reward_value__gt=0,
            enable_reward=False,
        )
        if upgraded_goals.exists():
            self.stdout.write(f'找到 {upgraded_goals.count()} 个需要升级的目标：')
            for g in upgraded_goals:
                self.stdout.write(
                    f'  #{g.id} {g.title}: '
                    f'reward_value={g.reward_value} → '
                    f'enable_reward=True, default_reward_amount={g.reward_value}'
                )
            if not dry_run:
                with transaction.atomic():
                    for g in upgraded_goals:
                        Goal.objects.filter(id=g.id).update(
                            enable_reward=True,
                            default_reward_amount=g.reward_value,
                        )
                self.stdout.write(self.style.SUCCESS('目标设置升级完成'))
            else:
                self.stdout.write(self.style.WARNING('DRY-RUN 模式，未实际修改'))
        else:
            self.stdout.write('没有需要升级的目标')

        # ── 第二步：补发奖励 ──
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('=== 第二步：补发里程碑奖励 ==='))

        milestones = Milestone.objects.filter(
            status='completed',
            reward_synced=False,
        ).select_related('goal')

        if not milestones.exists():
            self.stdout.write(self.style.SUCCESS('没有需要同步的里程碑'))
            return

        self.stdout.write(f'找到 {milestones.count()} 个待同步里程碑：')
        for m in milestones:
            goal = m.goal
            reward = MilestoneRewardService._get_reward_amount(m)
            flag = goal.enable_reward and reward > 0
            self.stdout.write(
                f'  [{">" if flag else "x"}] #{m.id} {m.title} '
                f'(目标: {goal.title}, enable_reward={goal.enable_reward}, reward={reward}元)'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN 模式，未实际发放'))
            return

        # 重新读取（enable_reward 可能刚被更新）
        milestones = Milestone.objects.filter(
            status='completed',
            reward_synced=False,
        ).select_related('goal')

        service = MilestoneRewardService()
        issued = 0
        skipped = 0
        for m in milestones:
            result = service.complete_milestone(m)
            if result:
                self.stdout.write(
                    f'  ✓ #{m.id} {m.title} → 发放 {result["amount"]}元 '
                    f'(流水ID: {result["transaction_id"]})'
                )
                issued += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'  - #{m.id} {m.title} 跳过（奖励金额为0或已同步）')
                )
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'完成：发放 {issued} 个，跳过 {skipped} 个'
        ))
