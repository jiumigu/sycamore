"""自我运转 · 阶段分两层（v3.65.0 第 1 轮）

覆盖 `docs/赎回期并入自我运转-实施清单-20261102.md` §1.8 的 8 条，另加 3 条
边界（形态必须显式声明 / 长阶段复制 / 复制继承上级）。

核心不变量：
1. 最多两层；
2. 同一 `parent` 下只允许一个 open（**不是**全局唯一）；
3. KPI 只挂叶子 ⇒ 长阶段天然不产生 `SelfRunPeriod`；
4. `get_open_stage()` 返回**叶子**，绝不返回长阶段。
"""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunMetric, SelfRunPeriod, SelfRunStage
from apps.selfrun.services import (
    current_period_meta, get_open_long_stage, get_open_stage,
)

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


def _leaf(name='小阶段', **over):
    base = {
        'name': name,
        'start_date': str(timezone.localdate()),
        'metrics': [{'template_key': 'grow_hours', 'goal_value': 12, 'floor_value': 5}],
    }
    base.update(over)
    return base


def _long(name='三年赎回期', **over):
    base = {
        'name': name,
        'start_date': str(timezone.localdate()),
        'end_date': '2029-09-30',
        'is_long_stage': True,
        'ledger_config': {'pool_principal': 100000},
    }
    base.update(over)
    return base


def _post(client, payload):
    return client.post(f'{URL}/stages/', payload, format='json')


# ── 1. 长阶段：0 条 KPI 也能建，且只写 1 张表 ─────────────────
def test_create_long_stage_without_metrics(client):
    resp = _post(client, _long())
    assert resp.status_code == 201, resp.data
    body = resp.json()

    stage = SelfRunStage.objects.get()
    assert stage.parent_id is None
    assert stage.ledger_config == {'pool_principal': 100000}
    assert SelfRunMetric.objects.count() == 0
    # 🔴 只写了 stage 一张表（`_written` 把 0 行过滤掉）
    assert body['written'] == {'selfrun_stage': 1}
    # 出参三个派生字段
    assert body['stage']['is_long_stage'] is True
    assert body['stage']['children_count'] == 0
    assert body['stage']['parent_name'] is None


# ── 2. 长阶段带 KPI ⇒ 400（不许既汇总又判定）─────────────────
def test_long_stage_with_metrics_rejected(client):
    resp = _post(client, _long(metrics=[{'template_key': 'grow_hours'}]))
    assert resp.status_code == 400
    assert '长阶段只汇总' in resp.json()['detail']
    assert SelfRunStage.objects.count() == 0


# ── 3. 叶子阶段不给 KPI ⇒ 400（不静默变成长阶段）──────────────
def test_leaf_without_metrics_rejected(client):
    resp = _post(client, {'name': '忘填 KPI 的阶段', 'start_date': str(timezone.localdate())})
    assert resp.status_code == 400
    assert '至少要有一条 KPI' in resp.json()['detail']
    assert SelfRunStage.objects.count() == 0


# ── 4. 两层封顶：第三层 ⇒ 400 ────────────────────────────────
def test_nested_third_level_rejected(client):
    assert _post(client, _long()).status_code == 201
    long_stage = SelfRunStage.objects.get()

    assert _post(client, _leaf(parent=long_stage.id)).status_code == 201
    child = SelfRunStage.objects.get(parent=long_stage)

    resp = _post(client, _leaf(name='第三层', parent=child.id))
    assert resp.status_code == 400
    assert '只支持两层' in resp.json()['detail']
    assert SelfRunStage.objects.count() == 2


# ── 5. 长阶段开着时，另起一个顶级阶段 ⇒ 400 且给出做法 ─────────
def test_second_root_stage_rejected_with_hint(client):
    assert _post(client, _long()).status_code == 201
    resp = _post(client, _long(name='另一个长阶段'))
    assert resp.status_code == 400
    detail = resp.json()['detail']
    # 🔴 不能只说「已有进行中的阶段」—— 得说清「挂到它下面」
    assert '长阶段' in detail and '挂在它下面' in detail
    assert SelfRunStage.objects.count() == 1


# ── 6. 同一 parent 下第二个小阶段 ⇒ 400 ──────────────────────
def test_two_children_same_parent_rejected(client):
    assert _post(client, _long()).status_code == 201
    long_stage = SelfRunStage.objects.get()

    assert _post(client, _leaf('第一个', parent=long_stage.id)).status_code == 201
    resp = _post(client, _leaf('第二个', parent=long_stage.id))
    assert resp.status_code == 400
    assert '已有进行中的阶段' in resp.json()['detail']
    assert SelfRunStage.objects.filter(parent=long_stage).count() == 1


# ── 7. 长阶段与小阶段可**同时** open，且各自被正确取到 ─────────
def test_long_and_leaf_both_open(client):
    assert _post(client, _long()).status_code == 201
    long_stage = SelfRunStage.objects.get()
    assert _post(client, _leaf(parent=long_stage.id)).status_code == 201
    child = SelfRunStage.objects.get(parent=long_stage)

    assert long_stage.status == 'active'
    assert child.status == 'active'
    # 🔴 关键断言：期相关的一切都必须拿到**叶子**
    assert get_open_stage() == child
    assert get_open_long_stage() == long_stage


# ── 8. 只有长阶段时 get_open_stage 为 None（没 KPI 就没判定）───
def test_long_stage_alone_has_no_current_stage(client):
    assert _post(client, _long()).status_code == 201
    assert get_open_stage() is None
    assert get_open_long_stage() is not None


# ── 9. 长阶段不产生 Period：归档当期 ⇒ 400，且 0 行 ────────────
def test_long_stage_produces_no_period(client):
    assert _post(client, _long()).status_code == 201
    key = current_period_meta('weekly')[0]
    resp = client.post(
        f'{URL}/periods/close/',
        {'period_type': 'weekly', 'period_key': key}, format='json',
    )
    assert resp.status_code == 400
    assert '没有进行中的阶段' in resp.json()['detail']
    assert SelfRunPeriod.objects.count() == 0


# ── 10. 长阶段不能复制成跑 KPI 的阶段 ────────────────────────
def test_copy_long_stage_rejected(client):
    assert _post(client, _long()).status_code == 201
    long_stage = SelfRunStage.objects.get()
    resp = client.post(
        f'{URL}/stages/copy/',
        {'from_stage_id': long_stage.id, 'name': '复制品'}, format='json',
    )
    assert resp.status_code == 400
    assert '没有 KPI' in resp.json()['detail']


# ── 11. 复制小阶段 ⇒ 新阶段仍挂在同一个长阶段下 ────────────────
def test_copy_child_inherits_parent(client):
    assert _post(client, _long()).status_code == 201
    long_stage = SelfRunStage.objects.get()
    assert _post(client, _leaf(parent=long_stage.id)).status_code == 201
    child = SelfRunStage.objects.get(parent=long_stage)

    # 先收尾叶子，否则同 parent 下已有 open（🔴 收尾**必须写总结**）
    closed = client.post(
        f'{URL}/stages/{child.id}/close/',
        {'text': '第一个小阶段收尾'}, format='json',
    )
    assert closed.status_code == 200, closed.data
    resp = client.post(
        f'{URL}/stages/copy/',
        {'from_stage_id': child.id, 'name': '下一个'}, format='json',
    )
    assert resp.status_code == 201, resp.data
    copied = SelfRunStage.objects.get(pk=resp.json()['stage']['id'])
    assert copied.parent_id == long_stage.id
    assert copied.metrics.filter(status='active').count() == 1


# ── 12. 小阶段不能跑到上级阶段之外（区间必须落在父区间内）────────
#     为什么必须拦：长阶段的账本按**自己的起止**现算，跑出去的那几天
#     既不属于任何小阶段、也不会从长阶段汇总里消失 ——
#     「长阶段 = 小阶段之和」这条恒等式就此静默破掉。
def test_child_start_before_parent_rejected(client):
    parent = _post(client, _long()).json()['stage']
    resp = _post(client, _leaf('早于父', parent=parent['id'], start_date='2026-01-01'))
    assert resp.status_code == 400
    assert '早于上级阶段' in resp.json()['detail']


def test_child_end_after_parent_end_rejected(client):
    parent = _post(client, _long()).json()['stage']
    resp = _post(
        client,
        _leaf('晚于父终点', parent=parent['id'], end_date='2030-01-01'),
    )
    assert resp.status_code == 400
    assert '晚于上级阶段' in resp.json()['detail']


def test_child_inside_parent_accepted(client):
    parent = _post(client, _long()).json()['stage']
    resp = _post(
        client,
        _leaf('落在里面', parent=parent['id'], end_date='2026-12-31'),
    )
    assert resp.status_code == 201, resp.data
    assert SelfRunStage.objects.get(parent=parent['id']).end_date.isoformat() == '2026-12-31'


# ── 13. `shape` 过滤：分层后 `status=active` 有两行 ──────────────
#     「取第一条」会拿到长阶段（排序 -start_date, -id，起点相同按 id 大的在前），
#     页头于是显示「0 条 KPI」、周/月读一个永不判定的阶段 —— 而且不报错。
def test_list_shape_filter(client):
    parent = _post(client, _long()).json()['stage']
    assert _post(client, _leaf(parent=parent['id'])).status_code == 201

    leaf = client.get(f'{URL}/stages/?status=active&shape=leaf').json()
    assert [s['name'] for s in leaf] == ['小阶段']

    long_rows = client.get(f'{URL}/stages/?status=active&shape=long').json()
    assert [s['name'] for s in long_rows] == ['三年赎回期']

    # 不带 shape ⇒ 两行都在：这就是「漏带参数就取第一条」的真坑
    assert len(client.get(f'{URL}/stages/?status=active').json()) == 2

    assert client.get(f'{URL}/stages/?shape=nope').status_code == 400
