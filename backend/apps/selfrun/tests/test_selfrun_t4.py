"""自我运转 · T4 事后分析 —— 4 条（设计稿 §12 之 24–27）

⚠️ 首轮 T4 **只做骨架**（阶段总结 + 指纹写入 + 复制），趋势/断点/对比留 P1。
   所以 24 / 25 两条用「历史列表不重算」与「指纹分组」来钉住同样的判据 ——
   它们是不变量，不是接口形状。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunCheckin, SelfRunMetric, SelfRunPeriod, SelfRunStage
from apps.selfrun.services import _fingerprint_groups, compute_stage_summary
from apps.temporal.models import TaskMeta, TemporalTask

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def stage(client):
    today = timezone.localdate()
    resp = client.post(f'{URL}/stages/', {
        'name': '离职后 · 建造期',
        'start_date': str(today - dt.timedelta(days=today.weekday())),
        'metrics': [
            {'template_key': 'grow_hours'},
            {'template_key': 'xuanzhi'},
        ],
    }, format='json')
    assert resp.status_code == 201, resp.data
    return SelfRunStage.objects.get()


def _seed_temporal(name, l2, days_ago_list, hours=1.0):
    TaskMeta.objects.get_or_create(
        task_name=name, defaults={'activity_type': l2, 'default_attribution': '关系'},
    )
    today = timezone.localdate()
    for d in days_ago_list:
        TemporalTask.objects.create(
            task_name=name, start_time=timezone.make_aware(
                dt.datetime.combine(today - dt.timedelta(days=d), dt.time(9, 0)),
            ),
            duration_hours=hours, year=2026, mon='10', day=1,
        )


def _week_key(days_ago):
    ref = timezone.localdate() - dt.timedelta(days=days_ago)
    iso = ref.isocalendar()
    return f'{iso[0]}-W{iso[1]:02d}'


def _last_week_days_ago(offset=1):
    return timezone.localdate().weekday() + offset


def _close(client, key):
    return client.post(f'{URL}/periods/close/', {
        'period_type': 'weekly', 'period_key': key,
    }, format='json')


def _reading(period_or_dict, name):
    readings = (
        period_or_dict.readings if hasattr(period_or_dict, 'readings')
        else period_or_dict['readings']
    )
    return next(r for r in readings if r['name'] == name)


# ── 24. 历史列表不写库，且数值 == 逐期冻结值（不重算）─────────
def test_history_reuses_frozen_values_and_writes_nothing(client, stage):
    days = _last_week_days_ago(1)
    _seed_temporal('代码编程', '深度工作', [days], hours=3.0)
    key = _week_key(days)
    assert _close(client, key).status_code == 201
    period = SelfRunPeriod.objects.get(period_key=key)
    frozen = _reading(period, '成长小时数')['final_value']
    assert frozen == 3.0

    # 归档之后源又变了
    _seed_temporal('代码编程', '深度工作', [days + 1], hours=50.0)

    before = SelfRunPeriod.objects.count()
    resp = client.get(f'{URL}/periods/?period_type=weekly')
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)                       # 🔴 裸数组，不是 {count, results}

    row = next(p for p in data if p['period_key'] == key)
    assert row['readings'] is not None
    assert _reading(row, '成长小时数')['final_value'] == frozen   # 仍是 3.0，不重算
    assert SelfRunPeriod.objects.count() == before                # GET 不写库


# ── 25. 指纹分组：换过尺子就分成两组（不可直接比）─────────────
def test_fingerprint_groups_split_at_config_change(client, stage):
    grow = stage.metrics.get(template_key='grow_hours')

    key_older = _week_key(_last_week_days_ago(8))
    assert _close(client, key_older).status_code == 201
    fp1 = SelfRunPeriod.objects.get(period_key=key_older).config_fingerprint

    # 改底线 ⇒ 换尺子 ⇒ 指纹必变
    resp = client.patch(f'{URL}/metrics/{grow.id}/',
                        {'floor_value': 3, 'reason': 'calibrate'}, format='json')
    assert resp.status_code == 200, resp.data
    fp_after = __import__(
        'apps.selfrun.readers', fromlist=['config_fingerprint'],
    ).config_fingerprint(stage)
    assert fp_after != fp1

    key_newer = _week_key(_last_week_days_ago(1))
    assert _close(client, key_newer).status_code == 201

    periods = list(SelfRunPeriod.objects.order_by('period_start'))
    groups = _fingerprint_groups(periods)
    assert len(groups) == 2
    assert groups[0]['fingerprint'] != groups[1]['fingerprint']
    assert groups[0]['periods'] == [key_older]
    assert groups[1]['periods'] == [key_newer]


# ── 26. 复制阶段：指纹必然不同，且不复制 Period / Checkin ─────
def test_copy_stage_new_fingerprint_without_history(client, stage):
    from apps.selfrun.readers import config_fingerprint

    # 攒一点历史（一期归档 + 一笔手工）
    key = _week_key(_last_week_days_ago(1))
    assert _close(client, key).status_code == 201
    xuanzhi = stage.metrics.get(template_key='xuanzhi')
    assert client.post(f'{URL}/checkins/', {
        'metric': xuanzhi.id, 'value': 2,
    }, format='json').status_code == 201

    src_fp = config_fingerprint(stage)
    assert src_fp

    # 收尾原阶段，才能开新阶段
    client.post(f'{URL}/stages/{stage.id}/summary/', {'text': '第一阶段到这里'}, format='json')
    assert client.post(f'{URL}/stages/{stage.id}/close/', {}, format='json').status_code == 200

    resp = client.post(f'{URL}/stages/copy/', {
        'from_stage_id': stage.id, 'name': '第二期',
        'start_date': str(timezone.localdate()),
    }, format='json')
    assert resp.status_code == 201, resp.data
    body = resp.json()
    new = SelfRunStage.objects.get(name='第二期')

    # KPI 定义复制过来了
    assert new.metrics.count() == stage.metrics.count() == 2
    # 历史**不跟**：Period / Checkin 都留在原阶段
    assert new.periods.count() == 0
    assert SelfRunCheckin.objects.filter(metric__stage=new).count() == 0
    assert SelfRunPeriod.objects.filter(stage=stage).count() == 1
    # 🔴 指纹必然不同（算入了 stage.id）
    assert config_fingerprint(new) != src_fp
    # 界面上必须提醒「目标值仍是上一阶段的」
    assert '重设' in body['note']


# ── 27. 阶段总结：写话的同时冻结当时的数字 ────────────────────
def test_stage_summary_freezes_snapshot(client, stage):
    # 🔴 播种必须落在本周内且够新鲜：原 `_last_week_days_ago(1)` 落在上周日
    #    （早于 stage.start_date 整整一周），freshness_at 距今天 > 3 天
    #    ⇒ `state='stale'` ⇒ `verdict='unknown'`
    #    ⇒ compute_stage_summary 把这条读数踢出 avg 分母（avg 变 None，见 services.py:1321）。
    #    改成本周内的今天：新鲜度 0 天 + 落在阶段窗口内，读数才进 avg。
    days = 0
    _seed_temporal('代码编程', '深度工作', [days], hours=6.0)
    _close(client, _week_key(days))

    resp = client.post(f'{URL}/stages/{stage.id}/summary/',
                       {'text': '这段路你走过来了'}, format='json')
    assert resp.status_code == 200, resp.data
    assert resp.json()['written'] == {'selfrun_stage': 1}

    stage.refresh_from_db()
    snap = stage.summary_snapshot
    assert snap and snap['metrics']
    assert stage.summary_at is not None
    grow_snap = next(m for m in snap['metrics'] if m['name'] == '成长小时数')
    assert grow_snap['avg'] == 6.0

    # 之后改口径 ⇒ **快照不动**（那是「你写这句话时看到的数」）
    grow = stage.metrics.get(template_key='grow_hours')
    client.patch(f'{URL}/metrics/{grow.id}/', {'floor_value': 1}, format='json')
    stage.refresh_from_db()
    assert stage.summary_snapshot == snap

    # 而实时算的数字会跟着变 —— 两者刻意的分离
    live = compute_stage_summary(stage)
    live_grow = next(m for m in live['metrics'] if m['name'] == '成长小时数')
    live_snap_grow = next(m for m in snap['metrics'] if m['name'] == '成长小时数')
    assert live_grow['floor_value'] != live_snap_grow['floor_value']
