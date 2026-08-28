"""目标进度服务（由 services.py 拆分）"""

from datetime import date, timedelta

from .milestone_reward import MilestoneRewardService

class GoalProgressService:
    """目标进度计算服务"""

    @staticmethod
    def recalculate(goal):
        """重新计算目标综合进度

        有子目标时：进度 = 子目标平均进度
        无子目标时：进度 = 已完成里程碑数 / 总里程碑数 × 100
        """
        subs = goal.sub_goals.exclude(status='archived').exclude(status='abandoned')
        if subs.exists():
            total = sum(s.progress_percentage for s in subs)
            goal.progress_percentage = min(round(total / subs.count()), 100)
            GoalProgressService._auto_transition_status(goal)
            goal.save(update_fields=['progress_percentage', 'status'])
            # 如果自己有父目标，向上冒泡
            if goal.parent_goal_id:
                parent = goal.parent_goal
                GoalProgressService.recalculate(parent)
            return

        milestone_progress = GoalProgressService._milestone_progress(goal)
        goal.progress_percentage = min(milestone_progress, 100)
        GoalProgressService._auto_transition_status(goal)
        goal.save(update_fields=['progress_percentage', 'status'])

        # 所有里程碑完成 → 检查目标完成奖励
        if goal.progress_percentage >= 100 and not goal.milestones.exclude(status='completed').exists():
            MilestoneRewardService._check_goal_completion_bonus(goal)

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
    def _auto_transition_status(goal):
        """进度 100% 时自动流转状态为已完成"""
        if goal.progress_percentage >= 100 and goal.status == 'in-progress':
            goal.status = 'completed'

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
            log = action.completion_log
            if isinstance(log, dict):
                for d_str, done in log.items():
                    try:
                        d = date.fromisoformat(d_str)
                        if d >= since:
                            total_checkins += 1
                            if done:
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


