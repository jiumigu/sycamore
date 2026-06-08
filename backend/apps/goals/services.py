import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from apps.reward.services import RewardPoolService


class GoalProgressService:
    """目标进度计算服务"""

    @staticmethod
    def recalculate(goal):
        """重新计算目标综合进度

        进度 = 已完成里程碑数 / 总里程碑数 × 100
        """
        milestone_progress = GoalProgressService._milestone_progress(goal)

        goal.progress_percentage = min(milestone_progress, 100)
        goal.save(update_fields=['progress_percentage'])

    @staticmethod
    def _milestone_progress(goal):
        """里程碑维度进度：已完成里程碑占比"""
        milestones = goal.milestones.all()
        total = milestones.count()
        if total == 0:
            return 0
        completed = milestones.filter(status='completed').count()
        return int((completed / total) * 100)

    @staticmethod
    def _action_progress(goal, days=30):
        """行为维度进度：近期行为完成率"""
        actions = goal.actions.all()
        if not actions.exists():
            return 0

        since = date.today() - timedelta(days=days)
        total_checkins = 0
        completed_checkins = 0

        for action in actions:
            if not action.completion_log:
                continue
            for entry in action.completion_log:
                entry_date = entry.get('date')
                if entry_date:
                    try:
                        d = date.fromisoformat(entry_date)
                        if d >= since:
                            total_checkins += 1
                            if entry.get('completed'):
                                completed_checkins += 1
                    except (ValueError, TypeError):
                        continue

        if total_checkins == 0:
            return 0
        return int((completed_checkins / total_checkins) * 100)

    @staticmethod
    def batch_recalculate(goals):
        """批量重新计算进度"""
        for goal in goals:
            GoalProgressService.recalculate(goal)


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
        from .models import Goal

        if milestone.reward_synced:
            return None

        reward_amount = self._get_reward_amount(milestone)

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

            return {
                'amount': float(reward_amount),
                'transaction_id': tx.id,
            }

        return None

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

                from .models import Goal
                Goal.objects.filter(id=milestone.goal_id).update(
                    total_reward_issued=models.F('total_reward_issued') - reward_amount,
                )

                return {'clawback': float(reward_amount)}

        return None


class QuickGoalService:
    """快速创建目标+批量里程碑服务"""

    FREQUENCY_MONTHLY = 'monthly'
    FREQUENCY_QUARTERLY = 'quarterly'
    FREQUENCY_WEEKLY = 'weekly'

    @staticmethod
    def _generate_milestone_labels(name: str, year: int, frequency: str, milestone_prefix: str = '') -> list[str]:
        """生成里程碑名称列表"""
        prefix = milestone_prefix or name
        if frequency == QuickGoalService.FREQUENCY_MONTHLY:
            return [f'{m}月{prefix}' for m in range(1, 13)]
        elif frequency == QuickGoalService.FREQUENCY_QUARTERLY:
            return [f'Q{q}{prefix}' for q in range(1, 5)]
        elif frequency == QuickGoalService.FREQUENCY_WEEKLY:
            return [f'第{w}周{prefix}' for w in range(1, 53)]
        return []

    @staticmethod
    def _generate_milestone_date(year: int, frequency: str, index: int) -> tuple[date | None, date | None]:
        """生成里程碑的目标日期范围"""
        if frequency == QuickGoalService.FREQUENCY_MONTHLY:
            month = index + 1
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, last_day)
        elif frequency == QuickGoalService.FREQUENCY_QUARTERLY:
            start_month = (index * 3) + 1
            end_month = (index * 3) + 3
            last_day = calendar.monthrange(year, end_month)[1]
            return date(year, start_month, 1), date(year, end_month, last_day)
        elif frequency == QuickGoalService.FREQUENCY_WEEKLY:
            try:
                start = date.fromisocalendar(year, index + 1, 1)
                end = date.fromisocalendar(year, index + 1, 7)
                if end.year > year:
                    return None, None
                return start, end
            except (ValueError, OverflowError):
                return None, None
        return None, None

    @staticmethod
    @transaction.atomic
    def create_with_milestones(name: str, year: int, frequency: str, reward_per_milestone: Decimal,
                                milestone_prefix: str = '') -> dict:
        """创建目标并批量生成里程碑"""
        from .models import Goal, Milestone

        reward = reward_per_milestone if reward_per_milestone > 0 else Decimal('0')

        goal = Goal.objects.create(
            title=name,
            category='year',
            year=year,
            status='planning',
            priority='p2',
            enable_reward=reward > 0,
            default_reward_amount=reward,
            user_id=1,
            start_date=date(year, 1, 1),
            deadline=date(year, 12, 31),
        )

        labels = QuickGoalService._generate_milestone_labels(name, year, frequency, milestone_prefix)
        milestones = []
        for i, label in enumerate(labels):
            target_start, target_end = QuickGoalService._generate_milestone_date(year, frequency, i)
            m = Milestone.objects.create(
                goal=goal,
                title=label,
                status='pending',
                order_num=i + 1,
                target_date=target_end,
                reward_amount=reward if reward > 0 else None,
                reward_synced=False,
            )
            milestones.append(m)

        GoalProgressService.recalculate(goal)
        return {'goal': goal, 'milestones': milestones}


class GoalCloneService:
    """目标复制服务"""

    @staticmethod
    @transaction.atomic
    def clone(goal, name: str, copy_milestones: bool, copy_actions: bool):
        """复制目标及其关联数据"""
        from .models import Action, Milestone

        pk = goal.pk
        goal.pk = None  # 重置主键以创建新记录
        goal.title = name
        goal.status = 'planning'
        goal.progress_percentage = 0
        goal.total_reward_issued = 0
        goal.created_at = None
        goal.updated_at = None
        goal.save()

        new_goal = goal
        old_goal_id = pk

        if copy_milestones:
            for m in Milestone.objects.filter(goal_id=old_goal_id):
                m.pk = None
                m.goal = new_goal
                m.status = 'pending'
                m.completed_note = None
                m.reward_synced = False
                m.reward_issued_at = None
                m.reward_transaction_id = None
                m.created_at = None
                m.updated_at = None
                m.save()

        if copy_actions:
            for a in Action.objects.filter(goal_id=old_goal_id):
                a.pk = None
                a.goal = new_goal
                a.milestone = None  # 里程碑ID在新目标中不对应
                a.created_at = None
                a.updated_at = None
                a.save()

        GoalProgressService.recalculate(new_goal)
        return new_goal


