"""决策结论「取前 N 名」—— 多选结论的口径与写入闸门。

背景（2026-10-24）：原实现只输出**一个**主导倾向（按条数 → 加权 → 定义顺序取第一）。
真实决策常是「这几件事一起做」，需要结论能取前 2 / 前 3 名。

这里钉住的是**口径**而不是展示，因为这类功能最容易出的错是
「前端按一个规则排序、后端按另一个规则标注」，于是卡片说前 2 名是 A/B、
报告标出来的却是 C/D —— 两边都"看起来对"，对不上才知道错了。
"""
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.toolkit.models import DecisionTracker

TRACKERS_URL = '/api/toolkit/decision-trackers/'
RECORDS_URL = '/api/toolkit/decision-records/'


def _create(topic='离职第一个月做哪些项', lean_options=None, top_n=None):
    payload = {
        'topic': topic,
        'start_date': (date.today() - timedelta(days=10)).isoformat(),
        'end_date': (date.today() + timedelta(days=5)).isoformat(),
    }
    if lean_options is not None:
        payload['lean_options'] = lean_options
    if top_n is not None:
        payload['result_top_n'] = top_n
    return APIClient().post(TRACKERS_URL, payload, format='json')


def _record(tracker_id, tendency, intensity=3):
    payload = {
        'tracker': tracker_id,
        'record_date': date.today().isoformat(),
        'tendency': tendency,
        'reason': 'pytest 造数',
        'intensity': intensity,
    }
    resp = APIClient().post(RECORDS_URL, payload, format='json')
    assert resp.status_code == 201, resp.data
    return resp.data


def _preview(tracker_id):
    resp = APIClient().get(f'{TRACKERS_URL}preview/?tracker={tracker_id}')
    assert resp.status_code == 200, resp.data
    return resp.data['items'][0]


@pytest.mark.django_db
def test_top_two_takes_two_highest_by_count():
    """核心：N=2 时结论是票数最高的两项，且按名次返回"""
    tracker = _create(lean_options=['写公众号', '做产品', '学琴'], top_n=2)
    tid = tracker.data['id']
    _record(tid, '写公众号')
    _record(tid, '写公众号')
    _record(tid, '做产品')
    _record(tid, '学琴')

    item = _preview(tid)

    assert item['result_top_n'] == 2
    assert item['conclusion_keys'] == ['写公众号', '做产品']
    assert '取前 2 名' in item['conclusion']
    assert '写公众号 50.0%' in item['conclusion']
    # lean_tendency 仍是第一名，保持旧字段语义不变（多个调用方在读它）
    assert item['lean_tendency'] == '写公众号'


@pytest.mark.django_db
def test_default_tracker_stays_single_conclusion():
    """默认三项（互斥）只出一项结论：老数据的 result_top_n 落到 1，行为与改动前一致"""
    tracker = _create()
    tid = tracker.data['id']
    _record(tid, 'quit')
    _record(tid, 'quit')
    _record(tid, 'continue')

    item = _preview(tid)

    assert item['result_top_n'] == 1
    assert item['conclusion_keys'] == ['quit']
    assert '取前 2 名' not in item['conclusion']


@pytest.mark.django_db
def test_default_tracker_rejects_multi_choice():
    """默认三项传 N>1 必须报错，而不是静默压回 1

    「想继续 + 不想继续」同时成立讲不通；静默夹紧会让用户以为自己设了前 2 名。
    """
    resp = _create(top_n=2)

    assert resp.status_code == 400
    assert 'result_top_n' in resp.data


@pytest.mark.django_db
def test_top_n_cannot_exceed_option_count():
    """两个选项要「前 3 名」→ 报错（第 3 名只能是空位）"""
    resp = _create(lean_options=['A', 'B'], top_n=3)

    assert resp.status_code == 400
    assert '最多取前 2 项' in str(resp.data['result_top_n'])


@pytest.mark.django_db
def test_zero_record_option_does_not_take_a_slot():
    """0 次记录的选项不占名次：三选二时不能把没记过的项算进「前 2 名」"""
    tracker = _create(lean_options=['A', 'B', 'C'], top_n=2)
    tid = tracker.data['id']
    _record(tid, 'A')
    _record(tid, 'B')

    item = _preview(tid)

    assert item['conclusion_keys'] == ['A', 'B']
    assert 'C' not in item['conclusion_keys']


@pytest.mark.django_db
def test_report_marks_same_top_items_as_preview():
    """报告标的结论项必须与预览一致 —— 同一事实一把尺子"""
    tracker = _create(lean_options=['A', 'B', 'C'], top_n=2)
    tid = tracker.data['id']
    _record(tid, 'C')
    _record(tid, 'C')
    _record(tid, 'A')
    _record(tid, 'B')

    item = _preview(tid)
    report = APIClient().get(f'{TRACKERS_URL}{tid}/report/').data

    # `tendency_stats` 按**选项定义顺序**返回（进度条不能因票数变化而跳动），
    # 名次由 `rank` 单独给 —— 所以这里按 rank 重排后再与结论比。
    top_in_report = [
        s['tendency'] for s in
        sorted((s for s in report['tendency_stats'] if s['is_top']), key=lambda s: s['rank'])
    ]
    assert top_in_report == item['conclusion_keys'] == ['C', 'A']
    assert report['result_top_n'] == 2


@pytest.mark.django_db
def test_decide_accepted_options_stored_separately():
    """采纳多项：进 final_choices，不顶替手写的 final_decision"""
    tracker = _create(lean_options=['A', 'B', 'C'], top_n=2)
    tid = tracker.data['id']

    resp = APIClient().post(
        f'{TRACKERS_URL}{tid}/decide/',
        {'final_decision': '先做 A 和 B', 'adopted': ['A', 'B']},
        format='json',
    )

    assert resp.status_code == 200, resp.data
    assert resp.data['status'] == '已决策'
    assert resp.data['final_choices'] == ['A', 'B']
    assert resp.data['final_decision'] == '先做 A 和 B'


@pytest.mark.django_db
def test_decide_allows_empty_text_when_options_adopted():
    """只采纳、不写字也要能提交 —— 多选结论下「就按前 2 项办」是常见操作"""
    tracker = _create(lean_options=['A', 'B'], top_n=2)
    tid = tracker.data['id']

    resp = APIClient().post(
        f'{TRACKERS_URL}{tid}/decide/', {'adopted': ['A', 'B']}, format='json',
    )

    assert resp.status_code == 200, resp.data
    assert resp.data['final_choices'] == ['A', 'B']
    assert resp.data['final_decision'] == ''


@pytest.mark.django_db
def test_decide_rejects_unknown_option():
    """采纳的选项必须是本决策定义过的，避免存进一份拼错的结论"""
    tracker = _create(lean_options=['A', 'B'], top_n=2)
    tid = tracker.data['id']

    resp = APIClient().post(
        f'{TRACKERS_URL}{tid}/decide/', {'adopted': ['做产品']}, format='json',
    )

    assert resp.status_code == 400
    assert '不是本决策的倾向选项' in resp.data['error']


@pytest.mark.django_db
def test_decide_rejects_overlong_text_instead_of_truncating():
    """超 50 字报错，不静默截断"""
    tracker = _create()
    tid = tracker.data['id']

    resp = APIClient().post(
        f'{TRACKERS_URL}{tid}/decide/', {'final_decision': '很' * 51}, format='json',
    )

    assert resp.status_code == 400
    assert '50' in resp.data['error']


@pytest.mark.django_db
def test_effective_top_n_is_clamped_at_model_level():
    """绕过接口直接写库时的兜底：默认三项恒为 1，自定义选项不超选项数"""
    tracker = DecisionTracker.objects.create(
        user_id=1, topic='直写测试',
        start_date=date.today(), end_date=date.today() + timedelta(days=5),
        lean_options=['A', 'B'], result_top_n=5,
    )
    assert tracker.effective_top_n() == 2

    tracker.lean_options = None
    assert tracker.effective_top_n() == 1
