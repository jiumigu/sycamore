"""自我运转 · T2 执行 —— 9 条（设计稿 §12 之 7–14；13b 为本轮新增）"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunCheckin, SelfRunMetric, SelfRunMetricLog, SelfRunPeriod, SelfRunStage
from apps.selfrun.services import compute_metric_reading
from apps.temporal.models import TaskMeta, TemporalTask

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def stage(client):
    """建一个含 4 条 KPI 的阶段：成长(auto) / 社交(auto_plus_manual) / 宣纸(manual) / 收入(auto)"""
    today = timezone.localdate()
    resp = client.post(f'{URL}/stages/', {
        'name': '测试阶段',
        'start_date': str(today - dt.timedelta(days=today.weekday())),
        'metrics': [
            {'template_key': 'grow_hours'},
            {'template_key': 'social_days'},
            {'template_key': 'xuanzhi'},
        ],
    }, format='json')
    assert resp.status_code == 201, resp.data
    return SelfRunStage.objects.get()


def _metric(stage, key):
    return stage.metrics.get(template_key=key)


def _aware(day, hour=9):
    return timezone.make_aware(dt.datetime.combine(day, dt.time(hour, 0)))


def _seed_temporal(name, l2, days_ago_list, hours=1.0):
    TaskMeta.objects.get_or_create(
        task_name=name, defaults={'activity_type': l2, 'default_attribution': '关系'},
    )
    today = timezone.localdate()
    for d in days_ago_list:
        TemporalTask.objects.create(
            task_name=name, start_time=_aware(today - dt.timedelta(days=d)),
            duration_hours=hours, year=2026, mon='10', day=1,
        )


# ── 7. auto 型没有补记入口 ───────────────────────────────────
def test_auto_metric_rejects_checkin(client, stage):
    grow = _metric(stage, 'grow_hours')
    assert grow.source_kind == 'auto'
    resp = client.post(f'{URL}/checkins/', {
        'metric': grow.id, 'value': 3, 'note': '想补记',
    }, format='json')
    assert resp.status_code == 400
    assert '没有补记入口' in str(resp.json())
    assert SelfRunCheckin.objects.count() == 0


# ── 8. manual 型的 auto_value 恒为 null（不是 0）─────────────
def test_manual_metric_auto_value_is_null(client, stage):
    xuanzhi = _metric(stage, 'xuanzhi')
    start, end = timezone.localdate() - dt.timedelta(days=7), timezone.localdate()
    r = compute_metric_reading(xuanzhi, start, end)
    assert r['auto_value'] is None          # 🔴 null，不是 0
    assert r['manual_value'] == 0.0
    assert r['final_value'] == 0.0


# ── 9. auto=0 与 auto=null 序列化后可区分 ────────────────────
def test_zero_and_null_are_distinguishable(client, stage):
    resp = client.get(f'{URL}/periods/current/?period_type=weekly')
    readings = {r['name']: r for r in resp.json()['period']['readings']}

    grow = readings['成长小时数']
    assert grow['auto_value'] == 0.0 and grow['manual_value'] is None

    xuanzhi = readings['宣纸']
    assert xuanzhi['auto_value'] is None and xuanzhi['manual_value'] == 0.0

    # 两个都是「0 值」，但一个来自「源里真没有」，一个来自「根本没有自动源」
    assert grow['auto_value'] != xuanzhi['auto_value']


# ── 10. 自动 2 + 手工 1 ⇒ final=3，三个数都在 ─────────────────
def test_auto_plus_manual_merges_and_keeps_three_numbers(client, stage):
    social = _metric(stage, 'social_days')
    assert social.source_kind == 'auto_plus_manual'

    # 本周内造 2 天有「社交」记录
    _seed_temporal('人际交往', '社交', [0, 1], hours=1.0)

    resp = client.get(f'{URL}/periods/current/?period_type=weekly')
    readings = {r['name']: r for r in resp.json()['period']['readings']}
    row = readings['社交连接']
    assert row['auto_value'] == 2.0
    assert row['manual_value'] == 0.0
    assert row['final_value'] == 2.0

    # 补记 1 天
    ok = client.post(f'{URL}/checkins/', {
        'metric': social.id, 'value': 1, 'note': '线下聊过没记时间',
    }, format='json')
    assert ok.status_code == 201

    resp = client.get(f'{URL}/periods/current/?period_type=weekly')
    row = {r['name']: r for r in resp.json()['period']['readings']}['社交连接']
    assert row['auto_value'] == 2.0
    assert row['manual_value'] == 1.0
    assert row['final_value'] == 3.0          # 合并，不是替换


# ── 11. 冲销：原记录保留 + 不能冲销两次 ───────────────────────
def test_reverse_keeps_original_and_only_once(client, stage):
    xuanzhi = _metric(stage, 'xuanzhi')
    ck = SelfRunCheckin.objects.create(
        metric=xuanzhi, checkin_date=timezone.localdate(), value=2, note='',
    )
    resp = client.delete(f'{URL}/checkins/{ck.id}/')
    assert resp.status_code == 200
    body = resp.json()
    assert float(body['reversal']['value']) == -2.0

    # 原记录**仍在**（撤销 ≠ 删除）
    assert SelfRunCheckin.objects.filter(pk=ck.id).exists()
    assert SelfRunCheckin.objects.count() == 2
    # 求和回到 0
    r = compute_metric_reading(
        xuanzhi, timezone.localdate() - dt.timedelta(days=1),
        timezone.localdate() + dt.timedelta(days=1),
    )
    assert r['final_value'] == 0.0

    # 同一笔不能冲销两次
    again = client.delete(f'{URL}/checkins/{ck.id}/')
    assert again.status_code == 409


# ── 12. 改 goal ⇒ 新增 MetricLog，Metric 行数不变（id 稳定）──
def test_goal_change_logs_without_new_metric_row(client, stage):
    grow = _metric(stage, 'grow_hours')
    metric_count = SelfRunMetric.objects.count()
    logs_before = SelfRunMetricLog.objects.filter(metric=grow).count()

    resp = client.patch(f'{URL}/metrics/{grow.id}/', {
        'goal_value': 10, 'reason': 'calibrate', 'reason_note': '预期不现实',
    }, format='json')
    assert resp.status_code == 200, resp.data
    body = resp.json()
    assert body['written'] == {'selfrun_metric': 1, 'selfrun_metric_log': 1}

    assert SelfRunMetric.objects.count() == metric_count      # 🔴 行数不变
    grow.refresh_from_db()
    assert float(grow.goal_value) == 10.0
    assert grow.id == _metric(stage, 'grow_hours').id         # metric_id 稳定

    logs = SelfRunMetricLog.objects.filter(metric=grow).order_by('id')
    assert logs.count() == logs_before + 1
    last = logs.last()
    assert last.action == 'goal_changed' and last.field_name == 'goal_value'
    assert float(last.from_value) == 12.0 and float(last.to_value) == 10.0
    assert last.reason == 'calibrate'


# ── 13. GET /periods/current/ 不写库 ─────────────────────────
def test_current_period_get_writes_nothing(client, stage):
    assert SelfRunPeriod.objects.count() == 0
    resp = client.get(f'{URL}/periods/current/?period_type=weekly')
    assert resp.status_code == 200
    body = resp.json()
    assert body['written'] == {}
    assert body['live'] is True
    assert body['period']['id'] is None           # 虚拟对象
    assert SelfRunPeriod.objects.count() == 0     # 🔴 翻页没有产生行


# ── 13b. 还没有阶段时，也要说清「本周是哪一周」 ───────────────
def test_current_period_without_stage_still_reports_key(client):
    """🔴 「当期是哪一期」与有没有阶段**无关**，两个分支必须同形。

    少了 `period_key` ⇒ 前端 `undefined` ⇒「本周状态」与「本月状态」两页
    长得一模一样（用户报的就是这个：「点三个菜单跳的都是同一个页面」）。

    同时钉住：周期标识只许后端一把尺子 —— 前端按 `Date` 自己算 ISO 周，
    跨年边界会**静默差一周**。
    """
    assert SelfRunStage.objects.count() == 0

    today = timezone.localdate()
    iso_y, iso_w, _ = today.isocalendar()

    body = client.get(f'{URL}/periods/current/?period_type=weekly').json()
    assert body['stage'] is None and body['period'] is None
    assert body['written'] == {}
    assert body['period_key'] == f'{iso_y}-W{iso_w:02d}'
    # 半开区间 [start, end)：今天必须落在里面，且 end 是**不含**的那一天
    assert body['period_start'] <= str(today) < body['period_end']

    month = client.get(f'{URL}/periods/current/?period_type=monthly').json()
    assert month['period_key'] == today.strftime('%Y-%m')
    assert month['period_start'] == today.strftime('%Y-%m-01')
    assert month['period_key'] != body['period_key']       # 两把尺子不同形


# ── 14. 心跳同一天只写一次 ───────────────────────────────────
def test_heartbeat_writes_once_per_day(client, stage):
    first = client.post(f'{URL}/heartbeat/', {'seen': True}, format='json')
    assert first.status_code == 200
    assert first.json()['written'] == {'selfrun_stage': 1}

    second = client.post(f'{URL}/heartbeat/', {'seen': True}, format='json')
    assert second.status_code == 200
    assert second.json()['written'] == {}          # 同日第二次不写库

    stage.refresh_from_db()
    assert stage.last_seen_at is not None
