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
    def ledger_progress(goal):
        """**账本口径**进度（只读，绝不落库）—— 用来对照手填的 `progress_percentage`。

        🔴 为什么需要第二个数：
           `Goal.progress_percentage` 是**手填输入**（`editable=False` 只是不进表单，
           接口仍可写）。它回答「我觉得我做到几成了」。
           而「里程碑完成率」是**有记录的账本**：完成几个 / 一共几个，可复算。
           两者并存时人一定会相信更乐观的那个（§114.3），所以必须**同时摆出来**。

        口径：
        - 有子目标 → 子目标 `progress_percentage` 的平均（子目标各自的手填值）
        - 否则 → 已完成里程碑 / 总里程碑
        - **两者都没有 → 返回 `None`**（「没有账本」≠「进度 0%」，§null/0 是三件事）

        与 `recalculate()` 的区别：这里**不写库、不改状态**，
        所以可以在 GET / 序列化器里安全调用。
        """
        subs = goal.sub_goals.exclude(status='archived').exclude(status='abandoned')
        if subs.exists():
            values = [s.progress_percentage for s in subs]
            return round(sum(values) / len(values)) if values else None
        total = goal.milestones.count()
        if not total:
            return None
        done = goal.milestones.filter(status='completed').count()
        return int(done / total * 100)

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


