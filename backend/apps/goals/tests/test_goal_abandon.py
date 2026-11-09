"""放弃目标 = PDCA 的 A（v3.62.41 补 C/A）

守四件事：
1. **一个动作只改一处真源** —— `Goal.status` 是状态真源，`GoalReview` 只留痕，不并存两个状态字段
2. **放弃理由必填** —— 放弃可以，但要能对自己解释；空理由不该静默通过
3. **里程碑不级联** —— 目标级决策不删子项（项目铁律：禁级联删除）
4. **复盘列表能按「月 + 类型」查** —— 否则前端判不出「本月是否已复盘」，又会变成 0 条死表
"""
import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.goals.models import Goal, GoalReview, Milestone

REVIEWS = '/api/goals/reviews/'


@pytest.fixture
def client():
    return APIClient()


def _goal(**kw):
    defaults = dict(
        user_id=1, title='测试目标', category='year',
        life_dimension='学习成长', status='in-progress',
    )
    defaults.update(kw)
    return Goal.objects.create(**defaults)


def _url(g):
    return f'/api/goals/goals/{g.id}/abandon/'


@pytest.mark.django_db
class TestAbandon:
    def test_sets_status_and_writes_one_review(self, client):
        g = _goal()
        r = client.post(_url(g), {'reason': '这个方向已经不成立了'}, format='json')
        assert r.status_code == 200

        g.refresh_from_db()
        assert g.status == 'abandoned'

        rev = GoalReview.objects.get(goal=g)
        assert rev.review_type == 'monthly'
        assert rev.what_blocked == '这个方向已经不成立了'
        assert rev.next_adjustment == '放弃'
        assert rev.review_date == dt.date.today()
        assert r.json()['review_id'] == rev.id

    def test_blank_reason_is_400_and_changes_nothing(self, client):
        g = _goal()
        r = client.post(_url(g), {'reason': '   '}, format='json')
        assert r.status_code == 400
        assert 'reason' in r.json()

        g.refresh_from_db()
        assert g.status == 'in-progress'
        assert GoalReview.objects.count() == 0

    def test_reason_over_200_is_400(self, client):
        g = _goal()
        r = client.post(_url(g), {'reason': '很' * 201}, format='json')
        assert r.status_code == 400
        g.refresh_from_db()
        assert g.status == 'in-progress'

    def test_already_abandoned_is_409(self, client):
        g = _goal(status='abandoned')
        r = client.post(_url(g), {'reason': '再放弃一次'}, format='json')
        assert r.status_code == 409
        assert GoalReview.objects.count() == 0

    def test_completed_cannot_be_abandoned(self, client):
        g = _goal(status='completed')
        r = client.post(_url(g), {'reason': '走完了还想放弃'}, format='json')
        assert r.status_code == 409
        g.refresh_from_db()
        assert g.status == 'completed'

    def test_milestones_survive(self, client):
        """放弃目标不删里程碑 —— 历史不能被一个状态改写"""
        g = _goal()
        Milestone.objects.create(goal=g, title='第一步', status='pending', order_num=1)
        Milestone.objects.create(goal=g, title='第二步', status='completed', order_num=2)

        r = client.post(_url(g), {'reason': '资源要收回'}, format='json')
        assert r.status_code == 200
        assert r.json()['milestone_count'] == 2
        assert Milestone.objects.filter(goal=g).count() == 2


@pytest.mark.django_db
class TestReviewListFilters:
    def test_filter_by_type_and_month(self, client):
        g = _goal()
        today = dt.date.today()
        GoalReview.objects.create(goal=g, review_type='monthly', review_date=today,
                                  what_blocked='本月放弃的那条')
        GoalReview.objects.create(goal=g, review_type='weekly', review_date=today,
                                  what_blocked='周回顾')

        r = client.get(REVIEWS, {'review_type': 'monthly', 'month': today.strftime('%Y-%m')})
        assert r.status_code == 200
        rows = r.json()
        rows = rows['results'] if isinstance(rows, dict) else rows
        assert len(rows) == 1
        assert rows[0]['review_type'] == 'monthly'

    def test_other_month_is_empty(self, client):
        g = _goal()
        GoalReview.objects.create(goal=g, review_type='monthly', review_date=dt.date(2026, 1, 5))
        r = client.get(REVIEWS, {'review_type': 'monthly', 'month': '2026-10'})
        rows = r.json()
        rows = rows['results'] if isinstance(rows, dict) else rows
        assert rows == []

    def test_bad_month_is_400_not_silent_empty(self, client):
        """参数出错必须报错 —— 静默返回空列表会让人以为「本月真的没复盘」"""
        r = client.get(REVIEWS, {'month': '2026/10'})
        assert r.status_code == 400
