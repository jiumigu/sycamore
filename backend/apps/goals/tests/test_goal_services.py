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


@pytest.mark.django_db
class TestMilestoneSorting:
    def _milestone(self, goal, title, status, target_date, order_num):
        return Milestone.objects.create(goal=goal, title=title, status=status,
                                        target_date=target_date, order_num=order_num)

    def test_milestone_list_sorting(self):
        from datetime import date
        from rest_framework.test import APIClient
        g = Goal.objects.create(user_id=1, title='排序目标', progress_percentage=0)
        self._milestone(g, '已完成', 'completed', date(2026, 7, 1), 1)
        self._milestone(g, '后天到期', 'in-progress', date(2026, 8, 30), 2)
        self._milestone(g, '无截止', 'pending', None, 3)
        self._milestone(g, '明天到期', 'in-progress', date(2026, 8, 29), 4)
        c = APIClient()
        r = c.get(f'/api/goals/milestones/?goal={g.id}')
        rows = r.data.get('results') or r.data
        order = [x['title'] for x in rows]
        assert order == ['明天到期', '后天到期', '无截止', '已完成'], order


@pytest.mark.django_db
class TestGoalNestedMilestoneSort:
    def test_goal_detail_milestones_prefetched_sorted(self):
        """目标详情接口（/api/goals/goals/<pk>/）的嵌套 milestones 走 Prefetch 智能排序"""
        from datetime import date
        from rest_framework.test import APIClient
        g = Goal.objects.create(user_id=1, title='嵌套排序', progress_percentage=0)
        Milestone.objects.create(goal=g, title='已完成沉底', status='completed',
                                 target_date=date(2026, 7, 1), order_num=1)
        Milestone.objects.create(goal=g, title='明天到期', status='in-progress',
                                 target_date=date(2026, 8, 29), order_num=2)
        Milestone.objects.create(goal=g, title='下周到期', status='pending',
                                 target_date=date(2026, 9, 5), order_num=3)
        Milestone.objects.create(goal=g, title='无截止', status='pending',
                                 target_date=None, order_num=4)
        c = APIClient()
        r = c.get(f'/api/goals/goals/{g.id}/')
        assert r.status_code == 200, r.status_code
        rows = [m['title'] for m in r.data['milestones']]
        assert rows == ['明天到期', '下周到期', '无截止', '已完成沉底'], rows


@pytest.mark.django_db
class TestMilestoneEditPreservesFields:
    """编辑操作（PATCH 部分更新）不得丢失未改动字段（回归：截止日期被清空问题）"""

    def _setup(self):
        from datetime import date
        g = Goal.objects.create(user_id=1, title='编辑保护', progress_percentage=0)
        m = Milestone.objects.create(
            goal=g, title='原始标题', status='in-progress',
            target_date=date(2026, 9, 30), order_num=3,
            description='原始描述', completed_note='原始备注',
        )
        return g, m

    def test_patch_title_keeps_target_date_and_other_fields(self):
        """只改标题，截止日期/状态/描述/备注必须保留"""
        from rest_framework.test import APIClient
        g, m = self._setup()
        c = APIClient()
        r = c.patch(f'/api/goals/milestones/{m.id}/', {'title': '新标题'}, format='json')
        assert r.status_code == 200
        m.refresh_from_db()
        assert m.title == '新标题'
        assert m.target_date is not None, 'target_date 被清空！'
        assert str(m.target_date) == '2026-09-30'
        assert m.status == 'in-progress'
        assert m.description == '原始描述'
        assert m.completed_note == '原始备注'
        assert m.order_num == 3

    def test_patch_status_keeps_target_date(self):
        """完成/状态变更也不得清空截止日期"""
        from rest_framework.test import APIClient
        g, m = self._setup()
        c = APIClient()
        r = c.patch(f'/api/goals/milestones/{m.id}/', {'status': 'completed'}, format='json')
        assert r.status_code == 200
        m.refresh_from_db()
        assert m.status == 'completed'
        assert str(m.target_date) == '2026-09-30', f'target_date 被清空: {m.target_date}'

    def test_patch_clears_target_date_only_when_explicit_null(self):
        """显式传 null 才允许清空截止日期（用户主动操作）"""
        from rest_framework.test import APIClient
        g, m = self._setup()
        c = APIClient()
        r = c.patch(f'/api/goals/milestones/{m.id}/', {'target_date': None}, format='json')
        assert r.status_code == 200
        m.refresh_from_db()
        assert m.target_date is None
