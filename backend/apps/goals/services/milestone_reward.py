"""里程碑奖励联动服务（由 services.py 拆分）"""

from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from apps.reward.services import RewardPoolService

class MilestoneRewardService:
    """里程碑奖励同步服务"""

    def __init__(self):
        self.reward_service = RewardPoolService()

    @staticmethod
    def _get_reward_amount(milestone) -> Decimal:
        """获取里程碑的实际奖励金额

        优先级：里程碑单独设置 > 目标默认值 > 系统默认 10 元
        """
        from django.conf import settings

        if milestone.reward_amount is not None and milestone.reward_amount > 0:
            return milestone.reward_amount

        goal = milestone.goal
        if goal.enable_reward and goal.default_reward_amount > 0:
            return goal.default_reward_amount

        goal = milestone.goal
        if goal.enable_reward and goal.reward_value > 0:
            return goal.reward_value

        return Decimal('10') if milestone.goal.enable_reward else Decimal('0')

    @transaction.atomic
    def complete_milestone(self, milestone) -> dict | None:
        """完成里程碑并发放奖励"""
        from ..models import Goal

        if milestone.reward_synced:
            return None

        reward_amount = self._get_reward_amount(milestone)
        result = None

        if reward_amount > 0:
            tx = self.reward_service.add_reward(
                source_id=milestone.id,
                source_type='milestone',
                amount=reward_amount,
                transaction_type='milestone_complete',
                description=f'完成里程碑「{milestone.title}」（{milestone.goal.title}），获得{reward_amount}元奖励',
            )

            milestone.reward_synced = True
            milestone.reward_issued_at = timezone.now()
            milestone.reward_transaction_id = tx.id
            milestone.save(update_fields=['reward_synced', 'reward_issued_at', 'reward_transaction_id'])

            # 更新目标的总奖励统计
            goal = milestone.goal
            Goal.objects.filter(id=goal.id).update(
                total_reward_issued=models.F('total_reward_issued') + reward_amount,
            )

            result = {
                'amount': float(reward_amount),
                'transaction_id': tx.id,
            }

        # 检查目标是否全部完成 → 发放目标完成奖励金
        self._check_goal_completion_bonus(milestone.goal)

        return result

    @staticmethod
    def _check_goal_completion_bonus(goal) -> None:
        """所有里程碑完成后发放目标完成奖励金（仅一次）"""
        from apps.reward.models import RewardTransaction

        if goal.goal_completion_bonus <= 0:
            return
        if goal.milestones.exclude(status='completed').exists():
            return
        if RewardTransaction.objects.filter(
            source_type='goal_complete',
            source_id=goal.id,
        ).exists():
            return

        service = RewardPoolService()
        service.add_reward(
            source_id=goal.id,
            source_type='goal_complete',
            amount=goal.goal_completion_bonus,
            transaction_type='goal_complete',
            description=f'🎉 目标完成：{goal.title}，获得{goal.goal_completion_bonus}元额外奖励',
        )

    @transaction.atomic
    def sync_on_update(self, milestone, old_status: str, old_reward: Decimal | None) -> dict | None:
        """里程碑更新时同步奖励

        处理两种场景：
        1. 状态变为 completed → 发放奖励
        2. 已完成里程碑的奖励金额变化 → 调整奖励池
        """
        # 场景 1：刚完成
        if milestone.status == 'completed' and not milestone.reward_synced:
            return self.complete_milestone(milestone)

        # 场景 2：已完成里程碑金额变化
        if milestone.reward_synced:
            new_reward = self._get_reward_amount(milestone)
            if new_reward != old_reward:
                delta = new_reward - old_reward
                if delta != 0:
                    description = f'里程碑奖励调整：{milestone.title}，{old_reward}→{new_reward}'
                    if delta > 0:
                        self.reward_service.adjust_reward(
                            source_id=milestone.id,
                            source_type='milestone',
                            delta=delta,
                            description=description,
                        )
                    else:
                        self.reward_service.deduct_reward(
                            source_id=milestone.id,
                            source_type='milestone',
                            amount=abs(delta),
                            reason='milestone_delete',
                            description=description,
                        )
                    milestone.reward_amount = new_reward
                    milestone.save(update_fields=['reward_amount'])

                    return {'adjustment': float(delta)}

        return None

    @transaction.atomic
    def sync_on_delete(self, milestone) -> dict | None:
        """删除里程碑时扣回已发放奖励"""
        if milestone.reward_synced:
            reward_amount = self._get_reward_amount(milestone)
            if reward_amount > 0:
                self.reward_service.deduct_reward(
                    source_id=milestone.id,
                    source_type='milestone',
                    amount=reward_amount,
                    reason='milestone_delete',
                    description=f'删除已完成里程碑「{milestone.title}」（{milestone.goal.title}），扣回{reward_amount}元',
                )

                from ..models import Goal
                Goal.objects.filter(id=milestone.goal_id).update(
                    total_reward_issued=models.F('total_reward_issued') - reward_amount,
                )

                return {'clawback': float(reward_amount)}

        return None


