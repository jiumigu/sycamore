"""自我运转 · 阶段类型（`run` 运转型 / `record` 记录型）与人生阶段时间轴（v3.64.56）

核心不变量：

1. **默认收紧**：`GET /stages/` 不传 `kind` 时**只给运转型** ——
   加这一维之前所有调用方都以为「这个接口 = 能跑 KPI 的阶段」，
   默认放开等于让「小学期」混进向导的上级阶段下拉、账本、已收尾表，
   而这三处**都不会报错**。
2. 记录型零 KPI、零 Period、恒 `closed`，且 `is_long_stage` 恒 `False`
   （否则「顶级 + 零 KPI」会把一条「小学期」判成长阶段）。
3. 记录型可以改 `start_date`、可以删；运转型两者都不可以。
4. 时间轴按起点**正序**，空档按**顶层区间并集**扫描（嵌套与重叠都不能算出负数天）。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.constants import (
    RECORD_STAGE_STATUS, STAGE_KIND_RECORD, STAGE_KIND_RUN,
)
from apps.selfrun.models import SelfRunStage
from apps.selfrun.services import (
    SelfRunError, create_record_stage, get_closed_stages, list_stages,
    stage_days_label, stage_range_label, stage_status_display, stage_timeline,
)

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'
TODAY = timezone.localdate()


@pytest.fixture
def client():
    return APIClient()


def _run_payload(name='离职适应期', **over):
    base = {
        'name': name,
        'start_date': str(TODAY),
        'metrics': [{'template_key': 'grow_hours', 'goal_value': 12, 'floor_value': 5}],
    }
    base.update(over)
    return base


def _record_payload(name='小学期', start='2000-09-01', **over):
    base = {'name': name, 'start_date': start, 'end_date': '2006-06-30'}
    base.update(over)
    return base


def _make_record(name='小学期', start=dt.date(2000, 9, 1), end=dt.date(2006, 6, 30), **over):
    return create_record_stage({
        'name': name, 'start_date': start, 'end_date': end, **over,
    })


# ── 1. 默认收紧：列表只给运转型 ────────────────────────────────
def test_list_defaults_to_run_kind(client):
    _make_record(name='小学期')
    r = client.post(f'{URL}/stages/', _run_payload(), format='json')
    assert r.status_code == 201, r.data

    names = [s['name'] for s in client.get(f'{URL}/stages/').data]
    assert names == ['离职适应期']
    assert '小学期' not in names


def test_list_kind_record_and_all(client):
    _make_record(name='小学期')
    client.post(f'{URL}/stages/', _run_payload(), format='json')

    only_record = client.get(f'{URL}/stages/?kind=record').data
    assert [s['name'] for s in only_record] == ['小学期']

    both = client.get(f'{URL}/stages/?kind=all').data
    assert sorted(s['name'] for s in both) == ['小学期', '离职适应期']
    # 序列化器要下发类型与显示词（前端不抄第三份中文表）
    rec = next(s for s in both if s['name'] == '小学期')
    assert rec['stage_kind'] == STAGE_KIND_RECORD
    assert rec['stage_kind_display'] == '记录型'


def test_list_rejects_bad_kind(client):
    resp = client.get(f'{URL}/stages/?kind=nope')
    assert resp.status_code == 400
    assert 'kind' in resp.data['detail']


# ── 2. 记录型：零 KPI、恒 closed、不是长阶段 ───────────────────
def test_create_record_stage_has_no_metric_and_is_closed(client):
    resp = client.post(f'{URL}/stages/records/', _record_payload(), format='json')
    assert resp.status_code == 201, resp.data
    s = resp.data['stage']
    assert s['stage_kind'] == STAGE_KIND_RECORD
    assert s['status'] == RECORD_STAGE_STATUS
    assert s['metric_count'] == 0
    assert s['is_long_stage'] is False      # 🔴 关键：不能被判成长阶段
    assert s['status_display'] == '已记录'
    assert resp.data['written'] == {'selfrun_stage': 1}
    assert SelfRunStage.objects.get(pk=s['id']).periods.count() == 0


def test_record_stage_without_end_date_shows_ongoing(client):
    resp = client.post(
        f'{URL}/stages/records/',
        {'name': '自我价值实现期', 'start_date': str(TODAY)},
        format='json',
    )
    assert resp.status_code == 201, resp.data
    s = resp.data['stage']
    assert s['status_display'] == '持续中'
    assert '持续中' in s['range_label']
    assert s['days_label'].startswith('到现在')


def test_record_stage_requires_start_date(client):
    resp = client.post(f'{URL}/stages/records/', {'name': '谋生期'}, format='json')
    assert resp.status_code == 400


def test_record_stage_rejects_non_record_parent(client):
    parent = client.post(f'{URL}/stages/', _run_payload(), format='json').data['stage']
    resp = client.post(
        f'{URL}/stages/records/',
        _record_payload(parent=parent['id']),
        format='json',
    )
    assert resp.status_code == 400
    assert '运转型' in resp.data['detail']


def test_record_child_is_grouped_not_counted_as_gap(client):
    """「求学阶段」下挂三段 —— 子阶段进 children，不参与空档扫描。"""
    college = _make_record(name='求学阶段', start=dt.date(2000, 9, 1), end=dt.date(2010, 6, 30))
    _make_record(
        name='小学期', start=dt.date(2000, 9, 1), end=dt.date(2006, 6, 30),
        parent=college.pk,
    )
    data = stage_timeline()
    assert [r['stage'].name for r in data['roots']] == ['求学阶段']
    assert [c.name for c in data['roots'][0]['children']] == ['小学期']
    # 小学期的日期区间不产生任何空档（它被父段包住）
    assert all(r['gap_before'] is None for r in data['roots'])


# ── 3. 记录型可改可删；运转型不可 ──────────────────────────────
def test_record_stage_start_date_is_editable(client):
    sid = _make_record().pk
    resp = client.patch(
        f'{URL}/stages/{sid}/',
        {'start_date': '2000-09-02', 'name': '小学（改）'},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    assert resp.data['stage']['start_date'] == '2000-09-02'
    assert resp.data['stage']['name'] == '小学（改）'
    assert set(resp.data['touched']) == {'start_date', 'name'}


def test_run_stage_start_date_still_rejected(client):
    sid = client.post(f'{URL}/stages/', _run_payload(), format='json').data['stage']['id']
    resp = client.patch(f'{URL}/stages/{sid}/', {'start_date': '2000-09-02'}, format='json')
    assert resp.status_code == 400
    assert '起点' in resp.data['detail']


def test_record_stage_deletable(client):
    sid = _make_record().pk
    resp = client.delete(f'{URL}/stages/{sid}/')
    assert resp.status_code == 200
    assert SelfRunStage.objects.filter(pk=sid).exists() is False


def test_run_stage_not_deletable(client):
    sid = client.post(f'{URL}/stages/', _run_payload(), format='json').data['stage']['id']
    resp = client.delete(f'{URL}/stages/{sid}/')
    assert resp.status_code == 400
    assert '收尾' in resp.data['detail']
    assert SelfRunStage.objects.filter(pk=sid).exists() is True


def test_record_stage_with_children_not_deletable(client):
    parent = _make_record(name='求学阶段', start=dt.date(2000, 9, 1), end=dt.date(2010, 6, 30))
    _make_record(name='小学期', start=dt.date(2000, 9, 1), end=dt.date(2006, 6, 30), parent=parent.pk)
    resp = client.delete(f'{URL}/stages/{parent.pk}/')
    assert resp.status_code == 400
    assert '子阶段' in resp.data['detail']


def test_copy_rejects_record_source(client):
    sid = _make_record().pk
    resp = client.post(
        f'{URL}/stages/copy/', {'from_stage_id': sid, 'name': '新阶段'}, format='json',
    )
    assert resp.status_code == 400
    assert '记录型' in resp.data['detail']


# ── 4. 「已收尾」不被记录型污染 ────────────────────────────────
def test_closed_list_excludes_record_stages(client):
    _make_record(name='小学期')
    assert list(get_closed_stages()) == []

    sid = client.post(f'{URL}/stages/', _run_payload(), format='json').data['stage']['id']
    client.patch(f'{URL}/stages/{sid}/', {'end_date': str(TODAY)}, format='json')
    # 收尾要求先留下阶段总结（一句话也算）—— 这是既有纪律，与本轮无关
    client.post(f'{URL}/stages/{sid}/summary/', {'text': '测验用'}, format='json')
    resp = client.post(f'{URL}/stages/{sid}/close/', {'end_date': str(TODAY)}, format='json')
    assert resp.status_code == 200, resp.data
    assert [s.name for s in get_closed_stages()] == ['离职适应期']


def test_list_stages_service_rejects_bad_shape():
    with pytest.raises(SelfRunError):
        list_stages(shape='weird')


# ── 5. 时间轴：正序 + 空档（含尾部） ───────────────────────────
def test_timeline_is_chronological(client):
    _make_record(name='大学期', start=dt.date(2010, 9, 1), end=dt.date(2014, 6, 30))
    _make_record(name='小学期', start=dt.date(2000, 9, 1), end=dt.date(2006, 6, 30))
    data = client.get(f'{URL}/stages/timeline/').data
    assert [r['stage']['name'] for r in data['roots']] == ['小学期', '大学期']


def test_timeline_reports_gap_between_two_stages(client):
    _make_record(name='小学期', start=dt.date(2000, 9, 1), end=dt.date(2006, 6, 30))
    # 2006-07-01 ~ 2010-08-31 中间空着
    _make_record(name='大学期', start=dt.date(2010, 9, 1), end=dt.date(2014, 6, 30))
    data = client.get(f'{URL}/stages/timeline/').data
    # 空档挂在**后一段**上（它之前空了多久），前端不用按日期自己配对
    assert data['roots'][0]['gap_before'] is None
    g = data['roots'][1]['gap_before']
    assert g['kind'] == 'between'
    assert g['start'] == '2006-07-01'
    assert g['end'] == '2010-08-31'
    # 闭区间天数：2006-07-01 ~ 2010-08-31 = 1523 天
    assert g['days'] == (dt.date(2010, 8, 31) - dt.date(2006, 7, 1)).days + 1
    # 总数 = 段间空档 + 尾部空档（最后一段 2014 结束，到今天也是空的）
    assert data['totals']['gap_days'] == g['days'] + data['tail_gap']['days']


def test_timeline_tail_gap_reaches_today(client):
    """所有阶段都已结束 ⇒ 从次日起到今天算「还没配置下一个阶段」。"""
    end = TODAY - dt.timedelta(days=10)
    _make_record(name='谋生期', start=end - dt.timedelta(days=100), end=end)
    data = client.get(f'{URL}/stages/timeline/').data
    tail = data['tail_gap']
    assert tail is not None
    assert tail['start'] == str(end + dt.timedelta(days=1))
    assert tail['end'] == str(TODAY)
    assert '还没配置' in tail['label']
    assert data['totals']['gap_days'] == tail['days']


def test_timeline_open_ended_stage_has_no_tail_gap(client):
    """有一条不设终点的阶段 ⇒ 它延伸到现在，后面没有「空档」可言。"""
    _make_record(name='自我价值实现期', start=TODAY - dt.timedelta(days=5), end=None)
    data = client.get(f'{URL}/stages/timeline/').data
    assert data['tail_gap'] is None


def test_timeline_overlapping_stages_do_not_produce_negative_gap(client):
    """两条并行（重叠）阶段 —— 相减会算出负数天，并集扫描不会。"""
    _make_record(name='谋生期', start=dt.date(2020, 1, 1), end=dt.date(2026, 10, 31))
    _make_record(name='自我价值实现期', start=dt.date(2024, 1, 1), end=dt.date(2028, 1, 1))
    data = client.get(f'{URL}/stages/timeline/').data
    assert all(r['gap_before'] is None for r in data['roots'])
    # 终点已到 2028（未来）⇒ 没有尾部空档
    assert data['tail_gap'] is None


def test_timeline_totals_split_by_kind(client):
    _make_record(name='小学期')
    client.post(f'{URL}/stages/', _run_payload(), format='json')
    data = client.get(f'{URL}/stages/timeline/').data
    assert data['totals']['all'] == 2
    assert data['totals']['run'] == 1
    assert data['totals']['record'] == 1
    assert data['totals']['first_start'] == '2000-09-01'
    # 枚举随接口下发
    assert {e['value'] for e in data['enum']['kind']} == {'run', 'record'}


def test_timeline_empty_is_legal(client):
    data = client.get(f'{URL}/stages/timeline/').data
    assert data['roots'] == []
    assert data['tail_gap'] is None
    assert data['totals']['first_start'] is None
    assert data['totals']['last_end'] is None
    assert data['totals']['gap_days'] == 0


# ── 6. 显示词（服务层一份） ────────────────────────────────────
def test_display_helpers_branch_on_kind():
    rec = _make_record()
    assert stage_status_display(rec) == '已记录'
    assert stage_range_label(rec) == '2000-09-01 ~ 2006-06-30（2129 天）'
    assert stage_days_label(rec) == '共 2129 天'

    run = SelfRunStage.objects.create(
        name='跑 KPI 的', start_date=TODAY, status='active', stage_kind=STAGE_KIND_RUN,
    )
    assert stage_status_display(run) == '进行中'
    assert stage_days_label(run) == '第 1 天'
    assert '不设终点' in stage_range_label(run)
