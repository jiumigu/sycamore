"""日程视图的里程碑口径 —— 已放弃目标的里程碑，**只筛掉还没完成的**

2026-10-26 实案：备考目标已放弃，但 `abandon` 明确「里程碑不动，不级联删子项」
（项目铁律），于是它名下 Day38–Day61 那批 pending 里程碑照旧排在日历上，
十月看起来像还有 24 件事要做 —— 一件也不会做了。

用户口径（原话）：「如果这个目标已经放弃了，**且对应里程碑还没完成**，
那对应的里程碑就不要出现在日程视图里了，**已经完成的还可以在历史日程中找到**」。

守四件事：
1. **只筛「已放弃 + 未完成」**：已完成的留着，历史日程要能翻回去看
2. **显式开关才过滤**：不能让「放弃」把目标详情页的里程碑也变没（静默丢数据）
3. 别的目标的里程碑不受牵连
4. 非真值参数不算开
"""
import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.goals.models import Goal, Milestone

MILESTONES = '/api/goals/milestones/'


@pytest.fixture
def client():
    return APIClient()


def _goal(title: str, status: str) -> Goal:
    return Goal.objects.create(
        user_id=1, title=title, category='year',
        life_dimension='学习成长', status=status,
    )


def _milestone(goal: Goal, title: str, day: int, status: str = 'pending') -> Milestone:
    return Milestone.objects.create(
        goal=goal, title=title, status=status,
        target_date=dt.date(2026, 10, day),
    )


def _titles(resp) -> list[str]:
    """接口是分页的（`{count, results}`），别假定裸数组 —— 前端也得两种都兜。"""
    body = resp.json()
    rows = body['results'] if isinstance(body, dict) else body
    return sorted(m['title'] for m in rows)


@pytest.mark.django_db
def test_hides_only_unfinished_milestones_of_abandoned_goal(client):
    """放弃目标下：未完成的隐去，**已完成的留在历史日程**。"""
    dead = _goal('已放弃的备考', 'abandoned')
    alive = _goal('在做的写作', 'in-progress')
    _milestone(dead, 'Day38 案例专项', 1)
    _milestone(dead, 'Day39 已经做完的那一步', 2, status='completed')
    _milestone(alive, '写完第一篇', 3)

    r = client.get(
        MILESTONES,
        {'target_date_year': 2026, 'target_date_month': 10, 'exclude_abandoned_goals': '1'},
    )
    assert r.status_code == 200
    # 已完成的里程碑必须还在 —— 否则翻历史日程时「那天做过什么」会凭空少一条
    assert _titles(r) == ['Day39 已经做完的那一步', '写完第一篇']


@pytest.mark.django_db
def test_in_progress_milestone_of_abandoned_goal_also_hidden(client):
    """`in-progress` 也算「还没完成」—— 判定只看 `status != 'completed'`。

    🔴 别写成 `status='pending'`：进行中的里程碑同样是「还欠着的事」，
    漏掉它等于规则只说了一半。
    """
    dead = _goal('已放弃的备考', 'abandoned')
    _milestone(dead, 'Day38 待开始', 1, status='pending')
    _milestone(dead, 'Day39 进行中', 2, status='in-progress')
    _milestone(dead, 'Day40 已完成', 3, status='completed')

    r = client.get(
        MILESTONES,
        {'target_date_year': 2026, 'target_date_month': 10, 'exclude_abandoned_goals': '1'},
    )
    assert _titles(r) == ['Day40 已完成']


@pytest.mark.django_db
def test_without_flag_nothing_is_hidden(client):
    """不带开关 ⇒ 一条都不少。

    🔴 这条是防「顺手改成默认过滤」的：目标详情页靠同一个接口取里程碑，
    默认过滤会让「放弃一条目标」后它的子项在页面上凭空消失 ——
    数据还在库里、界面说没有，属最难查的那类错。
    """
    dead = _goal('已放弃的备考', 'abandoned')
    _milestone(dead, 'Day38 案例专项', 1)

    r = client.get(MILESTONES, {'target_date_year': 2026, 'target_date_month': 10})
    assert r.status_code == 200
    assert _titles(r) == ['Day38 案例专项']


@pytest.mark.django_db
def test_other_goals_untouched(client):
    """多目标混排：只筛掉放弃目标的，其他目标（含已完成目标）照旧。"""
    dead = _goal('已放弃', 'abandoned')
    done = _goal('已完成目标', 'completed')
    doing = _goal('进行中目标', 'in-progress')
    planning = _goal('规划中目标', 'planning')
    _milestone(dead, 'A 死目标', 5)
    _milestone(done, 'B 已完成目标', 5)
    _milestone(doing, 'C 进行中', 5)
    _milestone(planning, 'D 规划中', 5)

    r = client.get(
        MILESTONES,
        {'target_date_year': 2026, 'target_date_month': 10, 'exclude_abandoned_goals': '1'},
    )
    assert _titles(r) == ['B 已完成目标', 'C 进行中', 'D 规划中']


@pytest.mark.django_db
def test_flag_accepts_only_truthy_values(client):
    """`0` / 空 不算开 —— 免得「传了就生效」这种隐式行为。"""
    dead = _goal('已放弃', 'abandoned')
    _milestone(dead, 'A 死目标', 5)

    r = client.get(
        MILESTONES,
        {'target_date_year': 2026, 'target_date_month': 10, 'exclude_abandoned_goals': '0'},
    )
    assert _titles(r) == ['A 死目标']
