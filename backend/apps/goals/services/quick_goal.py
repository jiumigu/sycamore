"""快速创建目标服务（由 services.py 拆分）"""

import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db import models, transaction

from .goal_progress import GoalProgressService

class QuickGoalService:
    """快速创建目标+批量里程碑服务"""

    FREQUENCY_DAILY = 'daily'
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_MONTHLY = 'monthly'
    FREQUENCY_QUARTERLY = 'quarterly'
    FREQUENCY_YEARLY = 'yearly'

    @staticmethod
    def _generate_milestone_labels(name: str, year: int, frequency: str, milestone_prefix: str = '',
                                    start_date: date | None = None, end_date: date | None = None,
                                    content_order: str = 'asc') -> list[str]:
        """生成里程碑名称列表

        自然顺序（i=0 对应最早日期），后续由 display_order 决定排列方向。
        """
        prefix = milestone_prefix or name
        if frequency == QuickGoalService.FREQUENCY_DAILY:
            if not start_date or not end_date:
                return []
            count = (end_date - start_date).days + 1
            if content_order == 'desc':
                return [f'{prefix}{(end_date - (start_date + timedelta(days=i))).days + 1}天' for i in range(count)]
            return [f'{prefix}{i + 1}天' for i in range(count)]
        elif frequency == QuickGoalService.FREQUENCY_WEEKLY:
            return [f'第{w}周{prefix}' for w in range(1, 53)]
        elif frequency == QuickGoalService.FREQUENCY_MONTHLY:
            return [f'{m}月{prefix}' for m in range(1, 13)]
        elif frequency == QuickGoalService.FREQUENCY_QUARTERLY:
            return [f'Q{q}{prefix}' for q in range(1, 5)]
        elif frequency == QuickGoalService.FREQUENCY_YEARLY:
            start_y = year
            end_y = year
            if start_date and end_date:
                start_y = start_date.year
                end_y = end_date.year
            return [f'{y}年{prefix}' for y in range(start_y, end_y + 1)]
        return []

    @staticmethod
    def _generate_milestone_date(year: int, frequency: str, index: int,
                                  start_date: date | None = None) -> date | None:
        """生成里程碑的目标日期"""
        if frequency == QuickGoalService.FREQUENCY_DAILY:
            if not start_date:
                return None
            return start_date + timedelta(days=index)
        if frequency == QuickGoalService.FREQUENCY_WEEKLY:
            try:
                end = date.fromisocalendar(year, index + 1, 7)
                return end if end.year == year else None
            except (ValueError, OverflowError):
                return None
        if frequency == QuickGoalService.FREQUENCY_MONTHLY:
            month = index + 1
            return date(year, month, calendar.monthrange(year, month)[1])
        elif frequency == QuickGoalService.FREQUENCY_QUARTERLY:
            end_month = (index * 3) + 3
            return date(year, end_month, calendar.monthrange(year, end_month)[1])
        elif frequency == QuickGoalService.FREQUENCY_YEARLY:
            if start_date:
                return date(start_date.year + index, 12, 31)
            return date(year + index, 12, 31)
        return None

    @staticmethod
    @transaction.atomic
    def create_with_milestones(name: str, year: int, frequency: str, reward_per_milestone: Decimal,
                                milestone_prefix: str = '',
                                start_date: date | None = None,
                                end_date: date | None = None,
                                content_order: str = 'asc',
                                display_order: str = 'asc') -> dict:
        """创建目标并批量生成里程碑"""
        from ..models import Goal, Milestone

        reward = reward_per_milestone if reward_per_milestone > 0 else Decimal('0')

        start = start_date or date(year, 1, 1)
        deadline = end_date or date(year, 12, 31)

        goal = Goal.objects.create(
            title=name,
            category='year',
            year=year,
            status='planning',
            priority='p2',
            enable_reward=reward > 0,
            default_reward_amount=reward,
            user_id=1,
            start_date=start,
            deadline=deadline,
        )

        labels = QuickGoalService._generate_milestone_labels(name, year, frequency, milestone_prefix,
                                                              start_date=start_date, end_date=end_date,
                                                              content_order=content_order)

        milestones = []
        for i, label in enumerate(labels):
            target = QuickGoalService._generate_milestone_date(year, frequency, i, start_date=start_date)
            m = Milestone.objects.create(
                goal=goal,
                title=label,
                status='pending',
                order_num=i + 1,
                target_date=target,
                reward_amount=reward if reward > 0 else None,
                reward_synced=False,
            )
            milestones.append(m)

        if display_order == 'desc':
            milestones.reverse()
            m = Milestone.objects.create(
                goal=goal,
                title=label,
                status='pending',
                order_num=i + 1,
                target_date=target,
                reward_amount=reward if reward > 0 else None,
                reward_synced=False,
            )
            milestones.append(m)

        GoalProgressService.recalculate(goal)
        return {'goal': goal, 'milestones': milestones}


