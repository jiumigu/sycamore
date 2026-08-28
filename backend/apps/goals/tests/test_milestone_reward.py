"""里程碑奖励联动测试 — apps.goals.services.MilestoneRewardService + goals.views 扣回"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.goals.models import Goal, Milestone
from apps.goals.services import GoalProgressService, MilestoneRewardService
from apps.reward.models import RewardPool, RewardTransaction


def _complete(ms: Milestone, goal: Goal) -> None:
    """模拟真实链路：状态置为完成 → 发放里程碑奖励 → 重算进度（触发完成奖励金检查）"""
    ms.status = 'completed'
    ms.save(update_fields=['status'])
    MilestoneRewardService().complete_milestone(ms)
    GoalProgressService.recalculate(goal)


@pytest.fixture
def goal() -> Goal:
    return Goal.objects.create(
        title='测试目标',
        category='year',
        life_dimension='学习成长',
        status='in-progress',
        enable_reward=True,
        default_reward_amount=Decimal('20'),
        reward_value=Decimal('0'),
        goal_completion_bonus=Decimal('0'),
    )


@pytest.fixture
def milestone(goal: Goal) -> Milestone:
    return Milestone.objects.create(goal=goal, title='里程碑A', status='pending')


def _balance() -> Decimal:
    return RewardPool.objects.first().balance if RewardPool.objects.exists() else Decimal('0')


@pytest.mark.django_db
def test_complete_milestone_issues_default_reward(goal: Goal, milestone: Milestone) -> None:
    """核心：完成里程碑发放目标默认奖励并标记同步"""
    result = MilestoneRewardService().complete_milestone(milestone)

    assert result == {'amount': 20.0, 'transaction_id': result['transaction_id']}
    milestone.refresh_from_db()
    assert milestone.reward_synced is True
    assert _balance() == Decimal('20.00')
    assert RewardTransaction.objects.filter(
        source_type='milestone', source_id=milestone.id, transaction_type='milestone_complete'
    ).count() == 1
    goal.refresh_from_db()
    assert goal.total_reward_issued == Decimal('20.00')


@pytest.mark.django_db
def test_complete_milestone_is_idempotent_no_double_pay(goal: Goal, milestone: Milestone) -> None:
    """核心：reward_synced 防重复——再次完成不再发奖"""
    MilestoneRewardService().complete_milestone(milestone)
    again = MilestoneRewardService().complete_milestone(milestone)

    assert again is None
    assert _balance() == Decimal('20.00')
    assert RewardTransaction.objects.filter(transaction_type='milestone_complete').count() == 1


@pytest.mark.django_db
def test_reward_amount_priority_milestone_over_goal(goal: Goal, milestone: Milestone) -> None:
    """优先级：里程碑单独设置 > 目标默认值"""
    milestone.reward_amount = Decimal('50')
    milestone.save()
    MilestoneRewardService().complete_milestone(milestone)
    assert _balance() == Decimal('50.00')


@pytest.mark.django_db
def test_reward_amount_falls_back_to_reward_value(goal: Goal) -> None:
    """优先级：无默认值时回退到 reward_value"""
    goal.default_reward_amount = Decimal('0')
    goal.reward_value = Decimal('15')
    goal.save()
    m = Milestone.objects.create(goal=goal, title='里程碑B', status='pending')
    MilestoneRewardService().complete_milestone(m)
    assert _balance() == Decimal('15.00')


@pytest.mark.django_db
def test_reward_disabled_issues_nothing(goal: Goal, milestone: Milestone) -> None:
    """边界：enable_reward=False → 不发奖、无流水、不标记同步"""
    goal.enable_reward = False
    goal.save()
    result = MilestoneRewardService().complete_milestone(milestone)
    milestone.refresh_from_db()
    assert result is None
    assert _balance() == Decimal('0')
    assert RewardTransaction.objects.count() == 0
    assert milestone.reward_synced is False


@pytest.mark.django_db
def test_api_complete_milestone_updates_total_issued(goal: Goal, milestone: Milestone) -> None:
    """核心：API 完成里程碑（views 路径）同步更新目标累计发奖统计"""
    client = APIClient()
    resp = client.patch(f'/api/goals/milestones/{milestone.id}/', {'status': 'completed'}, format='json')

    assert resp.status_code == 200
    goal.refresh_from_db()
    assert goal.total_reward_issued == Decimal('20.00')
    assert _balance() == Decimal('20.00')
    milestone.refresh_from_db()
    assert milestone.reward_synced is True


@pytest.mark.django_db
def test_cancel_completion_clawbacks_reward(goal: Goal, milestone: Milestone) -> None:
    """核心：取消完成（completed→pending）扣回已发奖励并重置同步标记"""
    _complete(milestone, goal)
    client = APIClient()
    resp = client.patch(f'/api/goals/milestones/{milestone.id}/', {'status': 'pending'}, format='json')

    assert resp.status_code == 200
    milestone.refresh_from_db()
    assert milestone.reward_synced is False
    assert milestone.reward_issued_at is None
    assert _balance() == Decimal('0.00')
    assert RewardTransaction.objects.filter(transaction_type='milestone_uncheck').count() == 1
    goal.refresh_from_db()
    assert goal.total_reward_issued == Decimal('0.00')


@pytest.mark.django_db
def test_delete_completed_milestone_clawbacks(goal: Goal, milestone: Milestone) -> None:
    """核心：删除已完成里程碑扣回奖励"""
    MilestoneRewardService().complete_milestone(milestone)
    result = MilestoneRewardService().sync_on_delete(milestone)

    assert result == {'clawback': 20.0}
    assert _balance() == Decimal('0.00')
    goal.refresh_from_db()
    assert goal.total_reward_issued == Decimal('0.00')


@pytest.mark.django_db
def test_goal_completion_bonus_only_when_all_done(goal: Goal) -> None:
    """核心：目标完成奖励金——全部里程碑完成后才发放"""
    goal.goal_completion_bonus = Decimal('100')
    goal.save()
    m1 = Milestone.objects.create(goal=goal, title='M1', status='pending')
    m2 = Milestone.objects.create(goal=goal, title='M2', status='pending')

    _complete(m1, goal)
    assert RewardTransaction.objects.filter(transaction_type='goal_complete').count() == 0  # M2 未完成

    _complete(m2, goal)
    assert RewardTransaction.objects.filter(transaction_type='goal_complete').count() == 1
    assert _balance() == Decimal('140.00')  # 20 + 20 + 100


@pytest.mark.django_db
def test_goal_completion_bonus_order_independent(goal: Goal) -> None:
    """核心：完成顺序无关——先完成最后一个，再补前面的，最终同样触发一次"""
    goal.goal_completion_bonus = Decimal('100')
    goal.save()
    m1 = Milestone.objects.create(goal=goal, title='M1', status='pending')
    m2 = Milestone.objects.create(goal=goal, title='M2', status='pending')

    _complete(m2, goal)
    assert RewardTransaction.objects.filter(transaction_type='goal_complete').count() == 0

    _complete(m1, goal)
    assert RewardTransaction.objects.filter(transaction_type='goal_complete').count() == 1


@pytest.mark.django_db
def test_goal_completion_bonus_not_reissued(goal: Goal) -> None:
    """边界：bonus 流水已存在时不重复发放（幂等）"""
    goal.goal_completion_bonus = Decimal('100')
    goal.save()
    m = Milestone.objects.create(goal=goal, title='M1', status='pending')

    _complete(m, goal)
    GoalProgressService.recalculate(goal)  # 再次重算不应重复发放

    assert RewardTransaction.objects.filter(transaction_type='goal_complete').count() == 1
    assert _balance() == Decimal('120.00')
