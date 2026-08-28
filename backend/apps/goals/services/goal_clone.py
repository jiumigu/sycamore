"""目标克隆服务（由 services.py 拆分）"""

from django.db import models, transaction

from .goal_progress import GoalProgressService

class GoalCloneService:
    """目标复制服务"""

    @staticmethod
    @transaction.atomic
    def clone(goal, name: str, copy_milestones: bool, copy_actions: bool):
        """复制目标及其关联数据"""
        from ..models import Action, Milestone

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


