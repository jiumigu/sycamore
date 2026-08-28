"""goals services 拆包后跨类引用回归（goal_clone/quick_goal 引用 GoalProgressService）"""
import pytest

from apps.goals.models import Goal, Milestone
from apps.goals.services import GoalCloneService, GoalProgressService, QuickGoalService, calculate_streak


@pytest.mark.django_db
class TestGoalServicesCrossRef:
    def _goal(self, title='测试目标'):
        return Goal.objects.create(user_id=1, title=title, progress_percentage=0)

    def test_goal_progress_service_recalc(self):
        """GoalProgressService 方法可调用（内部引用 MilestoneRewardService，回归跨类引用）"""
        g = self._goal()
        GoalProgressService.recalculate(g)  # 不抛 NameError 即通过
        g.refresh_from_db()
        assert g.progress_percentage == 0

    def test_goal_clone_importable(self):
        assert callable(GoalCloneService)

    def test_quick_goal_importable(self):
        assert callable(QuickGoalService)

    def test_calculate_streak(self):
        r = calculate_streak({'2026-08-01': True, '2026-08-02': True})
        assert r['longest'] == 2
