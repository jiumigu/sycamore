"""目标过程检查 = PDCA 的 C（v3.62.42）

守六件事：
1. **判定只由「时间进度 − 完成进度」与「停滞天数」得出**，阈值来自 constants，不在视图里拍
2. **长期目标（跨度 > 10 年）不算落后** —— 2069/2080 这类截止日按线性折算永远只走个位数
3. **`null` 不是 `0`**：算不出时间进度就下发 `None` + 原因码，不填 0 假装算过
4. **从未记录过进展 ≠ 正常** —— 没有动静的一律判停滞
5. **检查只读**：调用一次不能改动任何目标/里程碑
6. **`stats` 的逾期数不含已放弃/已归档**（v3.62.42 修的口径 bug）
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.goals.models import Goal, Milestone
from apps.goals.services import build_checkup

CHECKUP = '/api/goals/goals/checkup/'
STATS = '/api/goals/goals/stats/'


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


def _touch(goal, days_ago, status='pending'):
    """造一条里程碑，并把 updated_at 拨到 N 天前

    `updated_at` 是 auto_now，create 时写不进去，只能 update() 绕过。
    """
    m = Milestone.objects.create(goal=goal, title=f'm-{days_ago}', status=status)
    Milestone.objects.filter(pk=m.pk).update(
        updated_at=timezone.now() - dt.timedelta(days=days_ago),
    )
    return m


def _by_id(rows, goal_id):
    return next(r for r in rows if r['id'] == goal_id)


@pytest.mark.django_db
class TestVerdict:
    def test_behind_when_time_outpaces_progress(self):
        today = timezone.localdate()
        g = _goal(start_date=today - dt.timedelta(days=80),
                  deadline=today + dt.timedelta(days=20),
                  progress_percentage=25)
        _touch(g, 1)

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['time_progress'] == 80.0
        assert row['progress_gap'] == 55.0
        assert row['verdict'] == 'behind'
        assert row['verdict_label'] == '落后'
        assert row['days_left'] == 20

    def test_ahead_when_progress_outpaces_time(self):
        today = timezone.localdate()
        g = _goal(start_date=today - dt.timedelta(days=20),
                  deadline=today + dt.timedelta(days=80),
                  progress_percentage=60)
        _touch(g, 1)

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['verdict'] == 'ahead'

    def test_on_track_within_gap(self):
        today = timezone.localdate()
        g = _goal(start_date=today - dt.timedelta(days=50),
                  deadline=today + dt.timedelta(days=50),
                  progress_percentage=50)
        _touch(g, 1)

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['verdict'] == 'on_track'

    def test_gap_boundary_is_inclusive(self):
        """差正好 15 点就算落后（`>=`，不是 `>`）"""
        today = timezone.localdate()
        g = _goal(start_date=today - dt.timedelta(days=65),
                  deadline=today + dt.timedelta(days=35),
                  progress_percentage=50)
        _touch(g, 1)

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['time_progress'] == 65.0
        assert row['progress_gap'] == 15.0
        assert row['verdict'] == 'behind'

    def test_overdue_has_priority_over_stalled(self):
        today = timezone.localdate()
        g = _goal(start_date=today - dt.timedelta(days=100),
                  deadline=today - dt.timedelta(days=3),
                  progress_percentage=40)
        _touch(g, 90)  # 同时满足「停滞」

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['verdict'] == 'overdue'
        assert row['days_left'] == -3


@pytest.mark.django_db
class TestStall:
    def test_stalled_after_threshold(self):
        today = timezone.localdate()
        g = _goal(start_date=today - dt.timedelta(days=50),
                  deadline=today + dt.timedelta(days=50),
                  progress_percentage=50)
        _touch(g, 40)

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['days_since_activity'] == 40
        assert row['verdict'] == 'stalled'

    def test_recent_activity_is_not_stalled(self):
        today = timezone.localdate()
        g = _goal(start_date=today - dt.timedelta(days=50),
                  deadline=today + dt.timedelta(days=50),
                  progress_percentage=50)
        _touch(g, 3)

        assert _by_id(build_checkup()['rows'], g.id)['verdict'] == 'on_track'

    def test_never_recorded_is_stalled_not_on_track(self):
        """一条里程碑都没碰过 —— 「没记录」不能当成「没问题」"""
        today = timezone.localdate()
        g = _goal(start_date=today - dt.timedelta(days=10),
                  deadline=today + dt.timedelta(days=90))

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['days_since_activity'] is None
        assert row['last_activity_at'] is None
        assert row['verdict'] == 'stalled'
        assert build_checkup()['summary']['never_recorded'] >= 1


@pytest.mark.django_db
class TestHorizonAndNulls:
    def test_long_horizon_does_not_report_behind(self):
        """跨度 60 年 ⇒ 时间进度不可判，不能因此被标落后"""
        g = _goal(start_date=dt.date(2020, 1, 1), deadline=dt.date(2080, 12, 31))
        _touch(g, 1)

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['time_progress'] is None
        assert row['progress_gap'] is None
        assert row['time_progress_reason'] == 'long_horizon'
        assert row['verdict'] == 'on_track'  # 在动，如实说在动

    def test_long_horizon_still_can_be_stalled(self):
        g = _goal(start_date=dt.date(2020, 1, 1), deadline=dt.date(2080, 12, 31))
        _touch(g, 60)

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['verdict'] == 'stalled'

    def test_no_deadline_reason(self):
        g = _goal(start_date=dt.date(2026, 6, 17), deadline=None)
        _touch(g, 1)

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['time_progress'] is None
        assert row['time_progress_reason'] == 'no_deadline'
        assert row['days_left'] is None

    def test_invalid_span_reason(self):
        g = _goal(start_date=dt.date(2026, 5, 1), deadline=dt.date(2026, 5, 1))
        _touch(g, 1)

        assert _by_id(build_checkup()['rows'], g.id)['time_progress_reason'] == 'invalid_span'


@pytest.mark.django_db
class TestScope:
    def test_finished_goals_are_excluded(self):
        for st in ('completed', 'abandoned', 'archived'):
            _goal(title=f'finished-{st}', status=st)
        live = _goal(title='live', status='in-progress')

        ids = {r['id'] for r in build_checkup()['rows']}
        assert live.id in ids
        assert len(ids) == 1

    def test_paused_is_not_reported_as_stalled(self):
        g = _goal(status='paused')
        _touch(g, 120)

        row = _by_id(build_checkup()['rows'], g.id)
        assert row['verdict'] == 'paused'
        assert row['verdict_label'] == '已暂停'

    def test_summary_matches_rows(self):
        today = timezone.localdate()
        _goal(title='a', start_date=today - dt.timedelta(days=90),
              deadline=today + dt.timedelta(days=10), progress_percentage=10)
        _touch(_goal(title='b'), 90)

        data = build_checkup()
        s = data['summary']
        assert s['checked'] == len(data['rows'])
        assert s['problem'] == s['overdue'] + s['stalled'] + s['behind']
        assert s['problem'] <= s['checked']


@pytest.mark.django_db
class TestContract:
    def test_endpoint_returns_thresholds_and_rows(self, client):
        today = timezone.localdate()
        g = _goal(start_date=today - dt.timedelta(days=90),
                  deadline=today + dt.timedelta(days=10),
                  progress_percentage=10)
        _touch(g, 1)

        r = client.get(CHECKUP)
        assert r.status_code == 200
        body = r.json()

        # 阈值随结果下发，前端不硬编码
        assert {'as_of', 'stall_days', 'behind_gap', 'horizon_years'} <= set(body)
        assert body['stall_days'] == 30
        assert body['behind_gap'] == 15

        row = body['rows'][0]
        for key in ('id', 'title', 'progress', 'time_progress', 'progress_gap',
                    'days_since_activity', 'milestones_total', 'milestones_done',
                    'verdict', 'verdict_label', 'time_progress_reason'):
            assert key in row, f'序列化器白名单漏了 {key}'

    def test_sorted_by_severity(self, client):
        today = timezone.localdate()
        _goal(title='ok', start_date=today - dt.timedelta(days=50),
              deadline=today + dt.timedelta(days=50), progress_percentage=50)
        bad = _goal(title='overdue', start_date=today - dt.timedelta(days=90),
                    deadline=today - dt.timedelta(days=1), progress_percentage=10)
        _touch(bad, 1)

        rows = client.get(CHECKUP).json()['rows']
        assert rows[0]['id'] == bad.id

    def test_checkup_writes_nothing(self, client):
        g = _goal(status='in-progress')
        _touch(g, 100)
        before = Goal.objects.filter(pk=g.pk).values().first()

        client.get(CHECKUP)
        client.get(CHECKUP)

        assert Goal.objects.filter(pk=g.pk).values().first() == before


@pytest.mark.django_db
class TestStatsOverdueScope:
    def test_overdue_ignores_abandoned_and_archived(self, client):
        """v3.62.42 修：已放弃 / 已归档的截止日过了不是逾期"""
        today = timezone.localdate()
        past = today - dt.timedelta(days=5)
        _goal(title='放弃的', status='abandoned', deadline=past)
        _goal(title='归档的', status='archived', deadline=past)
        _goal(title='完成的', status='completed', deadline=past)
        live = _goal(title='真逾期', status='in-progress', deadline=past)

        body = client.get(STATS).json()
        assert body['overdue_goals'] == 1
        assert body['in_progress_goals'] >= 1
        assert live.status == 'in-progress'
