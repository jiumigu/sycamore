"""时段重叠提示（tasks/check_overlap）—— 手工新增/编辑前的「别重复记」提醒

口径（`services.find_overlaps`）：
- **不限任务名**：异名重叠也要提示（本库真实形态是「大段 + 段内细分」）
- 交集 ≥ 60s 才算一条 ⇒ 相接分段（10:00 结束 / 10:00:03 开始）不能报成重复
- `exclude_id` 排除自己，否则编辑任何一条都会「与自己重叠」

⚠️ 这些用例都写死在固定日期 `2026-10-21`：重叠是**绝对时间比较**，不需要"距今 N 天"，
写死反而能证明窗口判定与「今天」无关。
"""
from datetime import datetime

import pytest
from django.utils import timezone

from apps.temporal.models import TemporalTask


URL = '/api/temporal/tasks/check_overlap/'
DAY = '2026-10-21'


def _dt(hm: str) -> datetime:
    """支持 `HH:MM` 与 `HH:MM:SS` 两种写法（秒级用例要看抖动边界）。"""
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return timezone.make_aware(datetime.strptime(f'{DAY} {hm}', fmt))
        except ValueError:
            continue
    raise ValueError(f'无法解析的时间：{hm}')


def _mk(name: str, start: str, end: str):
    return TemporalTask.objects.create(
        task_name=name,
        start_time=_dt(start),
        end_time=_dt(end),
        duration_hours=(_dt(end) - _dt(start)).total_seconds() / 3600,
        year=2026, mon='10', day=21,
    )


def _get(query: str):
    from rest_framework.test import APIClient
    return APIClient().get(f'{URL}?{query}')


def _q(start: str, end: str, extra: str = ''):
    r = _get(f'start_time={DAY}%20{start}&end_time={DAY}%20{end}{extra}')
    assert r.status_code == 200, getattr(r, 'data', r.content)
    return r.data


@pytest.mark.django_db
class TestOverlapCheck:
    def test_no_overlap(self):
        _mk('看小说', '20:00', '21:00')
        data = _q('09:00', '10:00')
        assert data['has_overlap'] is False, data
        assert data['conflicts'] == []

    def test_other_task_name_also_reported(self):
        """异名重叠照样提示 —— 这正是「同一时段被记了两遍」的典型形态"""
        _mk('牛马工作', '08:00', '12:00')
        data = _q('09:50', '10:50')
        assert data['has_overlap'] is True, data
        assert len(data['conflicts']) == 1, data
        c = data['conflicts'][0]
        assert c['task_name'] == '牛马工作'
        assert c['overlap_minutes'] == 60, c
        assert c['same_name'] is False, c
        assert data['same_name_count'] == 0

    def test_same_name_flagged(self):
        """同名重叠 = 极可能重复新增，前端据此换更重的文案"""
        _mk('阅读思考', '09:00', '11:00')
        data = _q('10:00', '11:30', '&task_name=阅读思考')
        assert data['same_name_count'] == 1, data
        assert data['conflicts'][0]['same_name'] is True

    def test_touching_intervals_not_reported(self):
        """首尾相接（交集为 0）不算重叠 —— ATracker 分段就是这种形态"""
        _mk('上一段', '09:00', '10:00')
        data = _q('10:00', '11:00')
        assert data['has_overlap'] is False, data

    def test_sub_minute_jitter_ignored(self):
        """交集 < 60s 视为抖动：否则每条相接记录都会弹窗，提示会变成噪声"""
        _mk('上一段', '09:00', '10:00:30')
        data = _q('10:00:00', '11:00')
        assert data['has_overlap'] is False, data

    def test_fully_contained_counts_overlap_of_short_side(self):
        """新区间完全落在旧记录里：重叠 = 新区间自身时长"""
        _mk('牛马工作', '07:46', '18:00')
        data = _q('09:50', '10:50')
        assert data['conflicts'][0]['overlap_minutes'] == 60, data

    def test_exclude_id_skips_self(self):
        """编辑场景：把自己那条排除掉，否则「改个备注」也会提示重叠"""
        t = _mk('看小说', '20:00', '21:00')
        data = _q('20:10', '20:50', f'&exclude_id={t.id}')
        assert data['has_overlap'] is False, data

    def test_conflicts_sorted_by_overlap_desc(self):
        _mk('短', '09:00', '09:30')
        _mk('长', '09:00', '11:00')
        data = _q('09:00', '12:00')
        assert [c['task_name'] for c in data['conflicts']] == ['长', '短'], data

    def test_missing_params_400(self):
        r = _get('start_time=2026-10-21%2009:00')
        assert r.status_code == 400, r.data

    def test_bad_time_format_400(self):
        """参数写错必须报错，不能静默返回「没有重叠」"""
        r = _get('start_time=昨天&end_time=今天')
        assert r.status_code == 400, r.data

    def test_end_not_after_start_400(self):
        r = _get(f'start_time={DAY}%2010:00&end_time={DAY}%2009:00')
        assert r.status_code == 400, r.data

    def test_bad_exclude_id_400(self):
        r = _get(f'start_time={DAY}%2009:00&end_time={DAY}%2010:00&exclude_id=abc')
        assert r.status_code == 400, r.data
