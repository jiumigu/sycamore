"""手填进度 vs 账本进度：来源标注 + 对照值

🔴 第八轮审计 P0-3：`goals_goal.progress_percentage` 是手填字段，但界面上
   看起来像算出来的。一月一城手填 62% / 实际 18 城，读书计划手填 0% / 实际 8 本。
   ⇒ 接口必须同时给「来源」和「账本对照值」，否则人只会相信更乐观的那个（§114.3）。
"""
import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.goals.models import Goal, Milestone
from apps.goals.services import GoalProgressService

GOALS_URL = '/api/goals/goals/'


def _goal(**kw):
    today = dt.date.today()
    defaults = dict(
        title='测试目标', user_id=1, status='in-progress',
        start_date=today, deadline=today + dt.timedelta(days=30),
    )
    defaults.update(kw)
    return Goal.objects.create(**defaults)


# ══════════════════════════════════════════════════════════
# 服务层：ledger_progress 的口径
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_ledger_progress_is_milestone_ratio():
    goal = _goal()
    Milestone.objects.create(goal=goal, title='a', status='completed')
    Milestone.objects.create(goal=goal, title='b', status='pending')
    Milestone.objects.create(goal=goal, title='c', status='pending')
    Milestone.objects.create(goal=goal, title='d', status='pending')

    assert GoalProgressService.ledger_progress(goal) == 25


@pytest.mark.django_db
def test_ledger_progress_returns_none_without_any_ledger():
    """没有子目标、没有里程碑 ⇒ `None`（无账本），**不是 0%**。"""
    goal = _goal()
    assert GoalProgressService.ledger_progress(goal) is None


@pytest.mark.django_db
def test_ledger_progress_does_not_touch_db():
    """🔴 只读：算账本进度不能改 `progress_percentage`，也不改状态。"""
    goal = _goal(progress_percentage=62)
    Milestone.objects.create(goal=goal, title='a', status='pending')

    GoalProgressService.ledger_progress(goal)

    goal.refresh_from_db()
    assert goal.progress_percentage == 62
    assert goal.status == 'in-progress'


@pytest.mark.django_db
def test_ledger_progress_averages_sub_goals():
    parent = _goal(title='父目标')
    _goal(title='子1', parent_goal=parent, progress_percentage=80)
    _goal(title='子2', parent_goal=parent, progress_percentage=20)

    assert GoalProgressService.ledger_progress(parent) == 50


# ══════════════════════════════════════════════════════════
# 接口层：两个键必须一起下发
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_api_exposes_progress_source_and_ledger():
    goal = _goal(title='一月一城【100 座城市】', progress_percentage=62)
    Milestone.objects.create(goal=goal, title='第 1 座', status='completed')
    Milestone.objects.create(goal=goal, title='第 2 座', status='pending')

    resp = APIClient().get(GOALS_URL)
    rows = resp.data.get('results') if isinstance(resp.data, dict) else resp.data
    row = next(r for r in rows if r['id'] == goal.id)

    assert row['progress_percentage'] == 62
    assert row['progress_source'] == 'manual'
    assert row['progress_ledger'] == 50


@pytest.mark.django_db
def test_api_ledger_is_null_not_zero_when_no_ledger():
    """`null` 与 `0` 是两件事 —— 前端要能分清「—」和「0%」。"""
    goal = _goal(title='旅行计划')

    resp = APIClient().get(GOALS_URL)
    rows = resp.data.get('results') if isinstance(resp.data, dict) else resp.data
    row = next(r for r in rows if r['id'] == goal.id)

    assert row['progress_ledger'] is None
