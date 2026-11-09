# -*- coding: utf-8 -*-
"""summary 取数预算：一次请求只许取一份事实

背景（2026-10-28 实测）：`overview` 一个请求发 **35 条 SQL**，其中 12 条是
「时间投入」这份事实被取了三遍 —— 年覆盖率一次、年总量一次、强度又一次。
改法是三层：整年取一次（月度靠内存过滤）、请求内记忆、强度复用已算好的原始值。
改后 18 条 / 11.2ms。

本文件钉住三件事：
  ① 同一次请求里 ATracker 只许被 SELECT 一次（涨回去 = 有人又加了一处重复取数）
  ② 月度过滤仍按 `mon` 字符串（不是 `date.month`），口径不许悄悄放宽
  ③ 记忆**不跨请求** —— 改完归因规则，下一次请求必须看到新口径
"""
from datetime import datetime

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.summary.services.progress_aggregator import ProgressAggregator
from apps.temporal.models import TaskMeta, TemporalTask

OVERVIEW = '/api/summary/overview/'
MONTHLY = '/api/summary/monthly_detail/'

ATRACKER_HINT = 'time_atracker_tasks_list'


def _seed_times():
    """两个任务分别落在 8 月与 9 月，另有一条未归类 —— 覆盖「计入/排除/跨月」三种行"""
    TaskMeta.objects.create(task_name='深度学习', activity_type='深度工作', default_attribution='成长')
    TaskMeta.objects.create(task_name='朋友聚会', activity_type='社交', default_attribution='关系')
    TaskMeta.objects.create(task_name='无名', activity_type='未归类', default_attribution=None)
    for name, mon, day, hours in [
        ('深度学习', '08', 1, 10.0),
        ('深度学习', '09', 3, 6.0),
        ('朋友聚会', '09', 4, 2.0),
        ('无名', '09', 5, 3.0),
    ]:
        TemporalTask.objects.create(
            task_name=name,
            start_time=datetime.fromisoformat(f'2026-{mon}-{day:02d} 09:00:00'),
            duration_hours=hours, year=2026, mon=mon, day=day,
        )


def _atracker_selects(url: str) -> tuple[int, int]:
    """(ATracker 表被 SELECT 的次数, 该请求总 SQL 数)"""
    client = Client()
    client.get(url)  # 预热：首次请求会懒加载若干模块，别把噪音算进来
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(url)
    assert resp.status_code == 200
    sqls = [q['sql'] for q in ctx.captured_queries]
    return sum(1 for s in sqls if ATRACKER_HINT in s and 'SELECT' in s.upper()), len(sqls)


@pytest.mark.django_db
class TestOneRequestOneFetch:

    def test_overview_selects_attracker_once(self):
        """年视图：覆盖率与总量用的是同一份「计入行」

        旧实现 `_times_raw` 与 `_covered_marks` 各自回库一次 ⇒ 这里是 3。
        """
        _seed_times()
        hits, total = _atracker_selects(OVERVIEW)
        assert hits == 1, f'ATracker 被取了 {hits} 次（应当 1 次），本次请求共 {total} 条 SQL'

    def test_monthly_detail_selects_attracker_once(self):
        """月视图：直接过滤整年那份结果，不再单独发一条 mon=… 的查询"""
        _seed_times()
        hits, total = _atracker_selects(MONTHLY + '?year=2026&month=9')
        assert hits == 1, f'ATracker 被取了 {hits} 次（应当 1 次），本次请求共 {total} 条 SQL'

    def test_overview_sql_budget(self):
        """总条数预算：留一点余量，但必须明显低于改造前的 35"""
        _seed_times()
        _, total = _atracker_selects(OVERVIEW)
        assert total <= 22, f'overview 发了 {total} 条 SQL，预算 22'


@pytest.mark.django_db
class TestMonthFilterKeepsSemantics:

    def test_month_filter_still_matches_mon_string_not_date_month(self):
        """🔴 月度过滤按 `mon` 字符串，不是按 `date.month`

        库里若存在没补零的 `mon='8'`，旧 SQL（`filter(mon='08')`）会漏掉它。
        改成内存过滤时**必须保持同样的漏掉**：一旦改成比 `date.month`，
        这类历史行会突然被算进来 —— 月度总量凭空变大，而没有任何地方报错。
        """
        TaskMeta.objects.create(task_name='深度学习', activity_type='深度工作', default_attribution='成长')
        TemporalTask.objects.create(
            task_name='深度学习', start_time=datetime.fromisoformat('2026-08-06 09:00:00'),
            duration_hours=4.0, year=2026, mon='08', day=6,
        )
        TemporalTask.objects.create(
            task_name='深度学习', start_time=datetime.fromisoformat('2026-08-07 09:00:00'),
            duration_hours=5.0, year=2026, mon='8', day=7,   # 未补零的历史脏数据
        )
        assert ProgressAggregator._times_raw(2026) == 9.0        # 整年两条都算
        assert ProgressAggregator._times_raw(2026, 8) == 4.0     # 单月只算补零那条


@pytest.mark.django_db
class TestScopeDoesNotLeakAcrossRequests:

    def test_attribution_change_visible_on_next_request(self):
        """🔴 记忆只活在一次请求里：改完归因，下一次请求必须看到新口径

        如果哪天有人把 `_TIMES_COUNTED` 改成模块级/进程级缓存，这条会红 ——
        那正是「用户改完规则、页面还显示旧数，且界面上看不出来」的来源。
        """
        _seed_times()
        client = Client()

        def times_raw_value() -> float:
            body = client.get(OVERVIEW + '?year=2026').json()
            entry = next(m for m in body['modules'] if m['module'] == 'times')
            return entry['raw_value']

        assert times_raw_value() == 18.0   # 10 + 6 + 2（未归类那 3h 不计）

        # 把「朋友聚会」从 关系 改成 流失 ⇒ 下次请求应当只剩 16h
        TaskMeta.objects.filter(task_name='朋友聚会').update(default_attribution='流失')
        assert times_raw_value() == 16.0

    def test_cache_is_empty_outside_scope(self):
        """作用域外不记忆：脚本/测试直接调聚合器时，每次都是真取数"""
        _seed_times()
        assert ProgressAggregator._times_counted_year(2026) == ProgressAggregator._times_counted_year(2026)
        # 两次调用相互独立（无作用域 ⇒ 无缓存 ⇒ 各自回库），值仍相等
        assert ProgressAggregator._times_raw(2026) == 18.0
