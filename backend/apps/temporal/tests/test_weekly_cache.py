"""周度时间缓存的年份范围（v3.60.33）。

本轮修的是**滚动窗口造成的静默缺口**，三条互相独立：

1. `refresh_weekly_cache` 原来按「今年 ± 5」遍历年份 ⇒ 2026 年跑时 **2020 整年
   （源表 190 条 / 40 周）永远进不了固化表**，而命令照旧打印「完成」；
2. 同一个 `today.year - 5` 也写在 `WeeklyTimeTrackingView` 的默认 `start_year` 里
   ⇒ 接口默认同样看不到最早那几年；
3. 命令只 `update_or_create`、**从不删行** ⇒ 随窗口逐年上移，出窗年份的旧值会
   **留在固化表里冒充现状**（「有值但陈旧」比「缺失」更难发现）。

对应断言：年份由数据决定 · 陈旧周被清理 · 接口默认范围覆盖到最早年份 ·
参数写错要 400 而不是静默回退。推导见 `.workbuddy/memory/TECH-NOTES.md` §68。
"""

import io
from datetime import datetime

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.temporal.models import TemporalTask, WeeklyTimeCache

URL = '/api/temporal/weekly-tracking/'


def _task(when: str, hours: float, name: str = '牛马工作'):
    """按 start_time 反推 year / week —— 与导入链路同一套口径（不另写一把尺子）"""
    start = timezone.make_aware(datetime.fromisoformat(when))  # USE_TZ=True ⇒ 必须 aware
    iso = start.isocalendar()
    return TemporalTask.objects.create(
        task_name=name, task_description='', start_time=start, end_time=start,
        duration_hours=hours, notes='', tags=None, task_type=name,
        year=start.year, mon=f'{start.month:02d}', day=start.day,
        week=iso[1], quarter=(start.month - 1) // 3 + 1, import_batch='test',
    )


def _refresh(*args) -> str:
    out = io.StringIO()
    call_command('refresh_weekly_cache', *args, stdout=out)
    return out.getvalue()


def _week_of(when: str) -> int:
    return datetime.fromisoformat(when).isocalendar()[1]


# ════════════════════════════════════════════════════════════════════════════
# 1. 年份由数据决定，不再有滚动下界
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestYearRangeIsDataDriven:
    def test_year_far_outside_old_window_gets_cached(self):
        """2018 远在「今年 − 5」之外 —— 也必须进固化表"""
        when = '2018-03-07T09:00:00'
        _task(when, 8.0)

        out = _refresh()

        row = WeeklyTimeCache.objects.get(year=2018, week=_week_of(when))
        assert row.total_hours == 8.0
        assert row.task_count == 1
        assert '2018' in out, '刷新年份要打印出来，否则「漏了一年」没人看得见'

    def test_earliest_source_year_equals_earliest_cached_year(self):
        """源表最早那年 == 固化表最早那年 ⇒ 不存在被窗口吃掉的年份"""
        _task('2016-01-05T09:00:00', 3.0)
        _task('2026-01-05T09:00:00', 4.0)

        _refresh()

        assert set(WeeklyTimeCache.objects.values_list('year', flat=True)) == {2016, 2026}


# ════════════════════════════════════════════════════════════════════════════
# 2. 源表没有的周 ⇒ 固化表跟着消失（不留「有值但陈旧」）
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestStaleWeeksArePruned:
    def test_week_without_source_row_is_removed(self):
        when = '2020-05-06T09:00:00'
        _task(when, 8.0)
        keep = _week_of(when)
        WeeklyTimeCache.objects.create(year=2020, week=keep, total_hours=8.0, task_count=1)
        WeeklyTimeCache.objects.create(year=2020, week=keep + 1, total_hours=99.0, task_count=9)

        out = _refresh()

        weeks = set(WeeklyTimeCache.objects.filter(year=2020).values_list('week', flat=True))
        assert weeks == {keep}
        assert '清理陈旧 1 周' in out, '清理了几周要说出来'

    def test_year_with_no_source_at_all_is_cleared(self):
        """源表一点数据都没有的年份：残留行必须清掉，否则那年的数字会永远停在最后一次算出的值上"""
        WeeklyTimeCache.objects.create(year=2012, week=10, total_hours=42.0, task_count=5)

        _refresh()

        assert not WeeklyTimeCache.objects.filter(year=2012).exists()

    def test_existing_week_is_recomputed_not_kept(self):
        """陈旧值必须被重算覆盖（第 38 周 90.15 → 11.0 的实际形态）"""
        when_a, when_b = '2026-09-14T09:00:00', '2026-09-15T09:00:00'
        _task(when_a, 5.0)
        _task(when_b, 6.0)
        week = _week_of(when_a)
        assert _week_of(when_b) == week, '两条要落在同一周，否则这条用例测的不是同一件事'
        WeeklyTimeCache.objects.create(year=2026, week=week, total_hours=90.15, task_count=30)

        _refresh()

        row = WeeklyTimeCache.objects.get(year=2026, week=week)
        assert row.total_hours == 11.0
        assert row.task_count == 2


# ════════════════════════════════════════════════════════════════════════════
# 3. 干跑：先看会写什么、会清什么，再决定落不落库
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDryRun:
    def test_dry_run_writes_and_deletes_nothing(self):
        _task('2019-04-03T09:00:00', 7.5)
        WeeklyTimeCache.objects.create(year=2019, week=99, total_hours=1.0, task_count=1)

        out = _refresh('--dry-run')

        assert 'DRY-RUN' in out
        rows = list(WeeklyTimeCache.objects.filter(year=2019))
        assert [r.week for r in rows] == [99], '干跑不许写入新周'
        assert rows[0].total_hours == 1.0, '干跑不许清理陈旧周'


# ════════════════════════════════════════════════════════════════════════════
# 4. 接口默认范围覆盖到最早年份；参数写错要说出来
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestApiDefaultRange:
    def _seed(self):
        WeeklyTimeCache.objects.create(year=2016, week=1, total_hours=3.0, task_count=1)
        WeeklyTimeCache.objects.create(year=2026, week=41, total_hours=9.0, task_count=2)

    def test_default_range_covers_earliest_cached_year(self):
        self._seed()

        r = APIClient().get(URL)

        assert r.status_code == 200
        assert r.data['start_year'] == 2016, '默认下界必须跟着数据走，不能是「今年 − 5」'
        assert r.data['end_year'] == 2026
        assert {int(k) for k in r.data['data'].keys()} == {2016, 2026}

    def test_explicit_range_still_respected(self):
        self._seed()

        r = APIClient().get(URL, {'start_year': 2026})

        assert r.status_code == 200
        assert r.data['start_year'] == 2026
        assert [int(k) for k in r.data['data'].keys()] == [2026]

    def test_true_data_range_is_reported(self):
        """把真实范围摆出来 —— 让调用方能区分「这段没数据」与「被区间挡掉了」"""
        self._seed()

        r = APIClient().get(URL, {'start_year': 2026, 'end_year': 2026})

        assert r.data['data_range'] == {'start_year': 2016, 'end_year': 2026}

    def test_empty_cache_reports_none_range(self):
        """空表 ⇒ None，不是 0（`null` ≠ 0）"""
        r = APIClient().get(URL)

        assert r.status_code == 200
        assert r.data['data_range'] == {'start_year': None, 'end_year': None}
        assert r.data['data'] == {}

    @pytest.mark.parametrize('params', [
        {'start_year': 'abc'}, {'end_year': 'x'}, {'benchmark': '很多'},
    ])
    def test_bad_param_is_400_not_silent_default(self, params):
        """静默回退默认值会让「参数写错了」看起来像「这段时间没数据」"""
        r = APIClient().get(URL, params)

        assert r.status_code == 400
        assert 'detail' in r.data
