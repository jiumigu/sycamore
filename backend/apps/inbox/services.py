from datetime import datetime

from django.db import models, transaction
from django.utils import timezone


class ConverterService:
    """收件箱条目转换服务——将条目转为其他模块的数据"""

    @staticmethod
    def convert_to_goal(inbox_item, **extra):
        """转为目标，返回 (target_type, target_id)"""
        from apps.goals.models import Goal

        goal = Goal.objects.create(
            title=inbox_item.content,
            description=inbox_item.description or '',
            category='month',
            status='planning',
            priority=extra.get('priority', 'p2'),
            user_id=inbox_item.user_id,
        )
        return 'goal', goal.id

    @staticmethod
    def convert_to_milestone(inbox_item, **extra):
        """转为里程碑，返回 (target_type, target_id)"""
        from apps.goals.models import Goal, Milestone
        from apps.goals.services import GoalProgressService

        goal_id = extra.get('goal_id')
        if not goal_id:
            raise ValueError('转为里程碑需要指定目标ID')

        goal = Goal.objects.get(id=goal_id)
        milestone_name = extra.get('milestone_name', '') or inbox_item.content

        max_order = goal.milestones.aggregate(
            max_order=models.Max('order_num')
        )['max_order'] or 0

        milestone = Milestone.objects.create(
            goal=goal,
            title=milestone_name,
            status='pending',
            order_num=max_order + 1,
            target_date=extra.get('target_date') or None,
        )

        GoalProgressService.recalculate(goal)
        return 'milestone', milestone.id

    @staticmethod
    def convert_to_sugar(inbox_item, **extra):
        """转为能量清单模板，返回 (target_type, target_id)"""
        from apps.sugar.models import EnergyTemplate

        template = EnergyTemplate.objects.create(
            content=inbox_item.content,
            default_energy=extra.get('energy', 2),
            category=extra.get('category', 'daily'),
            is_system=False,
            user_id=inbox_item.user_id,
        )
        return 'sugar', template.id

    @classmethod
    def process(cls, inbox_item, action, **extra):
        """统一处理入口——执行转换并记录日志"""
        from .models import InboxProcessLog

        target_type = None
        target_id = None

        if action == 'complete':
            inbox_item.status = 'done'
            inbox_item.processed_at = timezone.now()

        elif action == 'convert_to_goal':
            target_type, target_id = cls.convert_to_goal(inbox_item, **extra)
            inbox_item.target_type = target_type
            inbox_item.target_id = target_id
            inbox_item.status = 'processed'
            inbox_item.processed_at = timezone.now()

        elif action == 'convert_to_milestone':
            target_type, target_id = cls.convert_to_milestone(inbox_item, **extra)
            inbox_item.target_type = target_type
            inbox_item.target_id = target_id
            inbox_item.status = 'processed'
            inbox_item.processed_at = timezone.now()

        elif action == 'convert_to_sugar':
            target_type, target_id = cls.convert_to_sugar(inbox_item, **extra)
            inbox_item.target_type = target_type
            inbox_item.target_id = target_id
            inbox_item.status = 'processed'
            inbox_item.processed_at = timezone.now()

        elif action == 'archive':
            inbox_item.status = 'archived'

        inbox_item.save()

        InboxProcessLog.objects.create(
            inbox=inbox_item,
            action=action,
            target_type=target_type,
            target_id=target_id,
            notes=extra.get('notes', ''),
            user_id=inbox_item.user_id,
        )

        return inbox_item
