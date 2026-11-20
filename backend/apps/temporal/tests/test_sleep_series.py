"""睡眠趋势（逐日折线）：口径与「今天的三条线」必须同一把尺子

守四件事：

① **按醒来那一刻归属**：23:40 睡 8h 算次日。按开始时刻算会让图整体左移一天，
   而且看起来完全合理 —— 这是最难靠肉眼发现的一种错。
② **没记录 ≠ 睡了 0 小时**：那天 `hours` 必须是 `None`/`unrecorded`，
   给 0 会在折线上画出一个不存在的谷底。
③ **上限也是判定线**：只有下限时睡 11.46 小时和睡 8 小时一样「达标」。
   上限 9.5 只在 `DAILY_GUARD_LINES` 里写一次，折线图和三条线共用。
④ **参数写错返 400**：静默回退成默认天数，会让「写错了」看起来像「这段时间没数据」。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.temporal.models import TaskMeta, TemporalTask
from apps.temporal.services import compute_daily_guards, compute_sleep_series

pytestmark = pytest.mark.django_db

SERIES = '/api/temporal/tasks/sleep-series/'


def _meta(name, role='sleep_night'):
    return TaskMeta.objects.create(
        task_name=name, activity_type='主动休息', default_attribution='维持',
        counts_growth=False, daily_role=role,
    )


def _rec(name, start, hours):
    naive = dt.datetime.strptime(start, '%Y-%m-%d %H:%M')
    TemporalTask.objects.create(
        task_name=name, start_time=timezone.make_aware(naive), duration_hours=hours,
        year=naive.year, mon=f'{naive.month:02d}', day=naive.day,
    )


def _day(series, date_str):
    return next(d for d in series['days'] if d['date'] == date_str)


class TestSleepSeries:
    def test_sleep_before_midnight_belongs_to_wakeup_day(self):
        """23:10 睡 7.5h ⇒ 醒来在次日 06:40，算次日。"""
        _meta('休息睡眠')
        _rec('休息睡眠', '2026-11-01 23:10', 7.5)

        s = compute_sleep_series(dt.date(2026, 11, 1), dt.date(2026, 11, 3))
        assert _day(s, '2026-11-01')['hours'] is None
        assert _day(s, '2026-11-02')['hours'] == 7.5

    def test_missing_day_is_null_not_zero(self):
        """没记录 ⇒ None + unrecorded。填 0 会让图出现假的谷底。"""
        _meta('休息睡眠')
        # 23:30 入睡、次日 07:30 醒 ⇒ 只算 11-03 有记录，11-01/11-02 都缺
        _rec('休息睡眠', '2026-11-02 23:30', 8.0)

        s = compute_sleep_series(dt.date(2026, 11, 1), dt.date(2026, 11, 3))
        missing = _day(s, '2026-11-02')
        assert missing['hours'] is None
        assert missing['status'] == 'unrecorded'
        assert missing['count'] == 0
        # 汇总里也不许把它算进平均值
        assert s['summary']['recorded_days'] == 1
        assert s['summary']['unrecorded_days'] == 2
        assert s['summary']['avg_hours'] == 8.0

    def test_oversleep_is_off_with_over_flag(self):
        """睡过头（> 上限 9.5）也算偏离，且 gap 要相对上限算，不是相对下限。"""
        _meta('休息睡眠')
        _rec('休息睡眠', '2026-11-02 22:00', 11.46)

        s = compute_sleep_series(dt.date(2026, 11, 3), dt.date(2026, 11, 3))
        d = _day(s, '2026-11-03')
        assert d['hours'] == 11.46
        assert d['status'] == 'off'
        assert d['over'] is True
        assert d['gap_hours'] == 2.0          # 11.46 - 9.5

    def test_short_sleep_is_off_without_over_flag(self):
        _meta('休息睡眠')
        _rec('休息睡眠', '2026-11-02 23:30', 6.5)

        s = compute_sleep_series(dt.date(2026, 11, 3), dt.date(2026, 11, 3))
        d = _day(s, '2026-11-03')
        assert d['status'] == 'off'
        assert d['over'] is False
        assert d['gap_hours'] == 1.5          # 8 - 6.5

    def test_two_records_same_wakeup_day_are_summed(self):
        """跨夜中断会拆成两条，醒来日相同的要合计，不能只取一条。"""
        _meta('休息睡眠')
        _rec('休息睡眠', '2026-11-02 23:00', 4.0)   # 醒来 03:00
        _rec('休息睡眠', '2026-11-03 03:10', 4.5)   # 醒来 07:40

        s = compute_sleep_series(dt.date(2026, 11, 3), dt.date(2026, 11, 3))
        d = _day(s, '2026-11-03')
        assert d['hours'] == 8.5
        assert d['count'] == 2
        assert d['status'] == 'ok'

    def test_unconfigured_role_gives_empty_series(self):
        """没标角色 ⇒ configured=False，每天都是 unrecorded（不是「睡得好」）。"""
        s = compute_sleep_series(dt.date(2026, 11, 1), dt.date(2026, 11, 2))
        assert s['configured'] is False
        assert all(d['status'] == 'unrecorded' for d in s['days'])
        assert s['summary']['recorded_days'] == 0
        assert s['summary']['avg_hours'] is None

    def test_thresholds_come_from_single_source(self):
        """折线图与「今天的三条线」共用同一份 spec：上限 9.5 必须两边一致。"""
        _meta('休息睡眠')
        _rec('休息睡眠', '2026-11-02 22:00', 11.46)

        s = compute_sleep_series(dt.date(2026, 11, 3), dt.date(2026, 11, 3))
        guard = compute_daily_guards(dt.date(2026, 11, 3))
        line = next(l for l in guard['lines'] if l['key'] == 'sleep')

        assert s['threshold_hours'] == line['threshold_hours'] == 8.0
        assert s['upper_hours'] == line['upper_hours'] == 9.5
        assert line['status'] == 'off'
        assert line['status_text'] == '偏离'
        assert line['gap_text'] == '超 2 小时'


class TestSleepSeriesApi:
    def test_default_window_is_30_days(self):
        _meta('休息睡眠')
        resp = APIClient().get(SERIES)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body['days']) == 30
        assert body['threshold_text'] == '8～9.5 小时'

    @pytest.mark.parametrize('query', ['?days=3', '?days=abc', '?days=400'])
    def test_bad_days_returns_400(self, query):
        """参数写错必须报错，不能静默按 30 天返回 —— 否则「写错」看起来像「没数据」。"""
        assert APIClient().get(SERIES + query).status_code == 400

    def test_bad_end_returns_400(self):
        resp = APIClient().get(SERIES + '?end=2026-13-01')
        assert resp.status_code == 400

    def test_end_pins_the_window(self):
        _meta('休息睡眠')
        _rec('休息睡眠', '2026-10-20 23:00', 8.0)

        resp = APIClient().get(SERIES + '?days=7&end=2026-10-21')
        body = resp.json()
        assert body['end'] == '2026-10-21'
        assert body['start'] == '2026-10-15'
        assert _day(body, '2026-10-21')['hours'] == 8.0
