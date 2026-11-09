"""自我运转 · 「改这条 KPI」里换取数方式（v3.64.31）—— 6 条

为什么这批用例必须存在：`source_kind` 以前只能在「建 KPI 时从模板挑」那一刻定下来，
建完就改不了（只能退役重建，而退役把手工登记一起带走）。现在开了这个口子，
三种静默失败都跟着来了：

1. **取数器拼错**（`works_cnt`）⇒ 取数时才炸 ⇒ 表现是「这条 KPI 某一页 500」，
   而不是「你刚点的那个按钮报错」。所以必须**当场 400 且不改库**。
2. **换了取数器没换 `agg`** ⇒ 界面写「从作品库取数 · 按手工求和」。
   `agg` 不影响数，所以不会有任何报错 —— 只能靠推导（`READER_AGG`）。
3. **手工项留着自动取数器** ⇒ 界面说「手工」，数却来自另一个模块。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunCheckin, SelfRunMetricLog, SelfRunStage
from apps.selfrun.readers import period_range
from apps.selfrun.services import compute_metric_reading
from apps.works.models import Work

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def stage(client):
    """一个含 3 条 KPI 的阶段：成长(auto) / 社交(auto_plus_manual) / 宣纸(manual)

    宣纸就是「建完之后才发现该自动取数」的那种典型 —— 本文件拿它当被试。
    """
    today = timezone.localdate()
    resp = client.post(f'{URL}/stages/', {
        'name': '换尺子测试阶段',
        'start_date': str(today - dt.timedelta(days=today.weekday())),
        'metrics': [
            {'template_key': 'grow_hours'},
            {'template_key': 'social_days'},
            {'template_key': 'xuanzhi'},
        ],
    }, format='json')
    assert resp.status_code == 201, resp.data
    return SelfRunStage.objects.get()


def _drawing(name):
    return Work.objects.create(name=name, kind='drawing')


# ── 1. 手工 → 自动 + 手工补记：换个取数器就够了 ────────────────
def test_switch_manual_to_auto_plus_manual(client, stage):
    metric = stage.metrics.get(template_key='xuanzhi')
    assert metric.source_kind == 'manual'
    assert metric.source_config == {'kind': 'manual_sum'}

    resp = client.patch(f'{URL}/metrics/{metric.id}/', {
        'source_kind': 'auto_plus_manual',
        'source_config': {'kind': 'works_count', 'where': {'work_kind': 'drawing'}},
        'reason': 'calibrate',
    }, format='json')
    assert resp.status_code == 200, resp.data

    metric.refresh_from_db()
    assert metric.source_kind == 'auto_plus_manual'
    assert metric.source_config == {'kind': 'works_count', 'where': {'work_kind': 'drawing'}}
    # 🔴 取数器 → 聚合方式跟着走：`works_count` 是「计数」，不是上一任的「手工求和」
    assert metric.agg == 'count'


# ── 2. 换完真的相加：作品库 2 件 + 手记 1 笔 = 3 ───────────────
def test_switch_then_reading_sums_auto_and_manual(client, stage):
    metric = stage.metrics.get(template_key='xuanzhi')
    today = timezone.localdate()

    _drawing('画一')
    _drawing('画二')
    # 切换**之前**记的那一笔，切换后必须仍然算数（它是补记，不是历史垃圾）
    assert client.post(f'{URL}/checkins/', {
        'metric': metric.id, 'value': 1, 'checkin_date': str(today),
    }, format='json').status_code == 201

    resp = client.patch(f'{URL}/metrics/{metric.id}/', {
        'source_kind': 'auto_plus_manual',
        'source_config': {'kind': 'works_count', 'where': {'work_kind': 'drawing'}},
    }, format='json')
    assert resp.status_code == 200, resp.data

    metric.refresh_from_db()
    start, end, _ = period_range('weekly', today)
    reading = compute_metric_reading(metric, start, end)
    assert reading['auto_value'] == 2
    assert reading['manual_value'] == 1
    assert reading['final_value'] == 3


# ── 3. 取数器拼错 ⇒ 当场 400，且**一个字都没写进库** ────────────
def test_unknown_reader_rejects_and_writes_nothing(client, stage):
    metric = stage.metrics.get(template_key='xuanzhi')
    before_logs = SelfRunMetricLog.objects.filter(metric=metric).count()

    resp = client.patch(f'{URL}/metrics/{metric.id}/', {
        'source_kind': 'auto',
        'source_config': {'kind': 'works_cnt'},     # 少一个 o
    }, format='json')
    assert resp.status_code == 400
    assert 'works_cnt' in resp.json()['detail']

    metric.refresh_from_db()
    # 「没换成」与「换成了空的」必须能分辨：这里连 source_kind 都不许动
    assert metric.source_kind == 'manual'
    assert metric.source_config == {'kind': 'manual_sum'}
    assert SelfRunMetricLog.objects.filter(metric=metric).count() == before_logs


# ── 4. 手工项不许挂着自动取数器（否则界面说手工、数来自作品库）──
def test_manual_forces_manual_sum_reader(client, stage):
    metric = stage.metrics.get(template_key='xuanzhi')

    resp = client.patch(f'{URL}/metrics/{metric.id}/', {
        'source_kind': 'manual',
        'source_config': {'kind': 'works_count', 'where': {'work_kind': 'drawing'}},
    }, format='json')
    assert resp.status_code == 200, resp.data

    metric.refresh_from_db()
    assert metric.source_kind == 'manual'
    assert metric.source_config == {'kind': 'manual_sum'}
    assert metric.agg == 'manual_sum'


# ── 5. 只改名字 ⇒ 取数方式一个字都不动（隐藏条件不许被抹掉）────
def test_rename_keeps_source_untouched(client, stage):
    metric = stage.metrics.get(template_key='social_days')
    before_kind = metric.source_kind
    before_config = dict(metric.source_config)
    assert before_config == {'kind': 'temporal_days', 'where': {'l2': ['社交']}}

    resp = client.patch(f'{URL}/metrics/{metric.id}/', {'name': '社交连接（改名）'},
                        format='json')
    assert resp.status_code == 200, resp.data

    metric.refresh_from_db()
    assert metric.source_kind == before_kind
    assert metric.source_config == before_config
    logs = SelfRunMetricLog.objects.filter(metric=metric, action='config_changed')
    assert [l.field_name for l in logs] == ['name']


# ── 6. 换尺子要留痕：`source_kind` 自己是一条日志 ────────────────
def test_source_kind_change_is_logged(client, stage):
    metric = stage.metrics.get(template_key='xuanzhi')

    resp = client.patch(f'{URL}/metrics/{metric.id}/', {
        'source_kind': 'auto_plus_manual',
        'source_config': {'kind': 'works_count'},
        'reason': 'calibrate',
    }, format='json')
    assert resp.status_code == 200, resp.data

    logs = {l.field_name: l for l in SelfRunMetricLog.objects.filter(metric=metric)}
    assert logs['source_kind'].from_value == 'manual'
    assert logs['source_kind'].to_value == 'auto_plus_manual'
    assert logs['source_kind'].reason == 'calibrate'
    # 取数器本体也各留一条（三个字段分开看，才知道「换的是哪一半」）
    assert 'source_config' in logs and 'agg' in logs
