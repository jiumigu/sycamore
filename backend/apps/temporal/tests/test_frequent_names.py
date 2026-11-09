"""最近常用任务名（frequent_names）—— 手工新增弹窗的快捷候选

口径：滚动 N 个自然月窗口内，按「记录次数」降序；同次数再按累计时长、最近使用。
所有数据都用「距今 N 天」构造，不写死日期 —— 否则测试会在几个月后静默失效
（数据滑出窗口，断言全空却仍然「通过」）。
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.temporal.models import TemporalTask


URL = '/api/temporal/tasks/frequent_names/'


def _mk(name: str, days_ago: int = 1, hours: float = 1.0):
    start = timezone.localtime() - timedelta(days=days_ago)
    return TemporalTask.objects.create(
        task_name=name,
        start_time=start,
        duration_hours=hours,
        year=start.year,
        mon=f'{start.month:02d}',
        day=start.day,
    )


def _get(query: str = ''):
    from rest_framework.test import APIClient
    r = APIClient().get(f'{URL}{query}')
    assert r.status_code == 200, getattr(r, 'data', r.content)
    return r.data


@pytest.mark.django_db
class TestFrequentNames:
    def test_orders_by_record_count_desc(self):
        """「频繁」按次数算：3 次 → 2 次 → 1 次"""
        for d in (1, 2, 3):
            _mk('A', days_ago=d)
        for d in (1, 2):
            _mk('B', days_ago=d)
        _mk('C', days_ago=1)

        items = _get()['items']
        assert [i['task_name'] for i in items] == ['A', 'B', 'C'], items
        assert items[0]['record_count'] == 3, items

    def test_window_excludes_old_records(self):
        """窗口外（120 天前）的任务即使次数更多也不出现"""
        for _ in range(5):
            _mk('很久以前', days_ago=120)
        _mk('最近', days_ago=1)

        names = [i['task_name'] for i in _get()['items']]
        assert '最近' in names, names
        assert '很久以前' not in names, names

    def test_tie_breaks_by_hours_then_recency(self):
        """同次数：累计时长多者先；时长也相同则最近用过的先"""
        _mk('长', days_ago=1, hours=2.0)
        _mk('长', days_ago=2, hours=2.0)      # 4h / 2 次
        _mk('短', days_ago=1, hours=0.5)
        _mk('短', days_ago=2, hours=0.5)      # 1h / 2 次
        _mk('昨天用过', days_ago=1, hours=1.0)
        _mk('前天用过', days_ago=2, hours=1.0)

        names = [i['task_name'] for i in _get()['items']]
        assert names.index('长') < names.index('短'), names
        assert names.index('昨天用过') < names.index('前天用过'), names

    def test_limit_respected(self):
        assert _get('?limit=2')['limit'] == 2
        for i in range(5):
            _mk(f'T{i}', days_ago=1)
        assert len(_get('?limit=2')['items']) == 2, _get('?limit=2')

    def test_empty_task_name_excluded(self):
        """历史空串不是可选择的任务名"""
        _mk('', days_ago=1)
        _mk('', days_ago=2)
        _mk('正常', days_ago=1)

        names = [i['task_name'] for i in _get()['items']]
        assert '' not in names, names
        assert '正常' in names, names

    def test_invalid_params_rejected(self):
        """参数写错必须说出来 —— 静默回退会让「写错了」看起来像「没有常用任务」"""
        from rest_framework.test import APIClient
        c = APIClient()
        for q in ('?months=0', '?months=25', '?limit=0', '?limit=31', '?months=abc', '?limit=x'):
            assert c.get(f'{URL}{q}').status_code == 400, q

    def test_empty_window_shape(self):
        """无数据：键集恒定、items 为空数组（前端据此决定是否显示标签组）"""
        d = _get()
        assert d['items'] == []
        assert set(d) == {'months', 'limit', 'window_start', 'items'}, d
        assert d['months'] == 3 and d['limit'] == 10, d

    def test_aggregation_not_split_by_meta_ordering(self):
        """同一任务名的多条记录必须按 task_name 聚合，不被拆成多行

        钉住的是**结果**（行数 / 次数 / 时长），不是某一行防御代码 ——
        本查询末尾的显式 `order_by(...)` 同时覆盖了外部表的默认排序，
        `start_time` 不会进 GROUP BY。若将来有人把它改成 `values_list().distinct()`
        又不显式清序，就会出现「次数恒为 1、排行变成哪个时刻最忙」，且不报错。
        """
        for d in (1, 2, 3, 4):
            _mk('写作', days_ago=d, hours=0.5)

        items = _get()['items']
        assert len(items) == 1, items
        assert items[0]['record_count'] == 4, items
        assert items[0]['total_hours'] == 2.0, items
