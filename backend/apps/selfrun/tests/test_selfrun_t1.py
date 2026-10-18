"""自我运转 · T1 制定配置 —— 6 条（设计稿 §12 之 1–6）"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunMetric, SelfRunMetricLog, SelfRunPeriod, SelfRunStage

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


def _payload(**over):
    base = {
        'name': '离职后 · 建造期',
        'start_date': str(timezone.localdate()),
        'note': '测试',
        'metrics': [
            {'template_key': 'grow_hours', 'goal_value': 12, 'floor_value': 5},
            {'template_key': 'output_count'},
            {'template_key': 'xuanzhi'},
        ],
    }
    base.update(over)
    return base


# ── 1. 生效写 3 张表，且在同一事务 ────────────────────────────
def test_create_stage_writes_three_tables(client):
    resp = client.post(f'{URL}/stages/', _payload(), format='json')
    assert resp.status_code == 201, resp.data
    body = resp.json()

    assert SelfRunStage.objects.count() == 1
    assert SelfRunMetric.objects.count() == 3
    assert SelfRunMetricLog.objects.count() == 3
    # `written` 让「数据流转」在运行时可见
    assert body['written'] == {
        'selfrun_stage': 1, 'selfrun_metric': 3, 'selfrun_metric_log': 3,
    }
    # 一步到位 active，不留 draft 残留
    assert SelfRunStage.objects.get().status == 'active'
    # 「创建」也是「一次配置变更」
    assert set(SelfRunMetricLog.objects.values_list('action', flat=True)) == {'created'}


# ── 2. 已有 active 阶段时再次创建 ⇒ 400 ───────────────────────
def test_second_stage_is_rejected(client):
    assert client.post(f'{URL}/stages/', _payload(), format='json').status_code == 201
    resp = client.post(f'{URL}/stages/', _payload(name='第二个'), format='json')
    assert resp.status_code == 400
    assert '已有进行中的阶段' in resp.json()['detail']
    assert SelfRunStage.objects.count() == 1        # 没有静默建第二个


# ── 3. goal < floor ⇒ 400 ────────────────────────────────────
def test_goal_lower_than_floor_is_rejected(client):
    bad = _payload(metrics=[
        {'template_key': 'grow_hours', 'goal_value': 3, 'floor_value': 5},
    ])
    resp = client.post(f'{URL}/stages/', bad, format='json')
    assert resp.status_code == 400
    assert '低于底线' in resp.json()['detail']
    assert SelfRunStage.objects.count() == 0        # 事务回滚，没有半截数据


# ── 4. start_date 生效后只读 ─────────────────────────────────
def test_start_date_is_read_only_after_activation(client):
    client.post(f'{URL}/stages/', _payload(), format='json')
    stage = SelfRunStage.objects.get()
    old = stage.start_date

    resp = client.patch(
        f'{URL}/stages/{stage.id}/', {'start_date': '2026-01-01'}, format='json',
    )
    assert resp.status_code == 400                  # 明确拒绝，不静默忽略、也不 500
    stage.refresh_from_db()
    assert stage.start_date == old

    # 但 note 可以改
    ok = client.patch(f'{URL}/stages/{stage.id}/', {'note': '改了备注'}, format='json')
    assert ok.status_code == 200
    stage.refresh_from_db()
    assert stage.note == '改了备注'


# ── 5. 试算接口不写任何表 ────────────────────────────────────
def test_preview_writes_nothing(client):
    client.post(f'{URL}/stages/', _payload(), format='json')
    before = (
        SelfRunStage.objects.count(), SelfRunMetric.objects.count(),
        SelfRunMetricLog.objects.count(), SelfRunPeriod.objects.count(),
    )
    resp = client.post(f'{URL}/metrics/preview/', {
        'period_type': 'weekly', 'source_kind': 'auto', 'agg': 'sum_hours',
        'source_config': {'kind': 'temporal_hours', 'where': {'l2': ['深度工作']}},
        'goal_value': 12, 'floor_value': 5, 'floor_options': [3, 5, 12],
    }, format='json')
    assert resp.status_code == 200, resp.data
    body = resp.json()
    assert body['written'] == {}
    assert len(body['rows']) == 11
    assert {'min', 'max', 'median', 'mean', 'count'} <= set(body['stats'])
    assert [o['floor'] for o in body['floor_options']] == [3, 5, 12]
    after = (
        SelfRunStage.objects.count(), SelfRunMetric.objects.count(),
        SelfRunMetricLog.objects.count(), SelfRunPeriod.objects.count(),
    )
    assert before == after


# ── 6. 起点非周一 ⇒ 该期 is_partial=True ─────────────────────
def test_non_monday_start_marks_partial_period(client):
    today = timezone.localdate()
    if today.weekday() == 0:
        pytest.skip('今天正好是周一，构造不出「起点在周中」的场景')

    client.post(f'{URL}/stages/', _payload(start_date=str(today)), format='json')
    resp = client.get(f'{URL}/periods/current/?period_type=weekly')
    assert resp.status_code == 200, resp.data
    period = resp.json()['period']

    # 当期是「本周」（周一起），而阶段从周中开始 ⇒ 这一期是残缺周
    assert period['is_partial'] is True
    assert period['period_start'] < str(today) or period['period_start'] == str(
        today - dt.timedelta(days=today.weekday())
    )
