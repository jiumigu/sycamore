"""决策追踪器测试 — 状态流转 / 日常记录 / 到期汇总报告"""
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.toolkit.models import DecisionRecord, DecisionTracker

TRACKERS_URL = '/api/toolkit/decision-trackers/'
RECORDS_URL = '/api/toolkit/decision-records/'


def _create_tracker(topic: str = '这份工作还值得继续吗', end_offset_days: int = 30) -> dict:
    start = date.today() - timedelta(days=10)
    end = date.today() + timedelta(days=end_offset_days)
    payload = {
        'topic': topic,
        'background': '观察工作满意度',
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
    }
    resp = APIClient().post(TRACKERS_URL, payload, format='json')
    assert resp.status_code == 201, resp.data
    return resp.data


def _add_record(tracker_id: int, tendency: str, reason: str = '', days_ago: int = 0) -> dict:
    payload = {
        'tracker': tracker_id,
        'record_date': (date.today() - timedelta(days=days_ago)).isoformat(),
        'tendency': tendency,
        'reason': reason,
        'intensity': '中',
    }
    resp = APIClient().post(RECORDS_URL, payload, format='json')
    assert resp.status_code == 201, resp.data
    return resp.data


@pytest.mark.django_db
def test_tracker_create_carry_default_status_and_record_count() -> None:
    """核心：新建追踪默认观察中；列表带 record_count/days_left"""
    data = _create_tracker()
    tracker = DecisionTracker.objects.get(id=data['id'])
    assert tracker.status == '观察中'
    assert data['record_count'] == 0
    assert data['days_left'] == 30


@pytest.mark.django_db
def test_record_create_attached_to_tracker() -> None:
    """核心：日常记录归属 tracker，倾向/强度/理由入库"""
    tracker = _create_tracker()
    _add_record(tracker['id'], 'continue', '双休稳定', days_ago=2)
    _add_record(tracker['id'], 'quit', '需求频繁变更', days_ago=1)
    rec = DecisionRecord.objects.filter(tracker_id=tracker['id']).order_by('-record_date').first()
    assert rec.tendency == 'quit'
    assert rec.reason == '需求频繁变更'
    assert rec.intensity == '中'
    assert tracker['id'] and DecisionRecord.objects.filter(tracker_id=tracker['id']).count() == 2


@pytest.mark.django_db
def test_expired_tracker_auto_marked_on_list() -> None:
    """核心：观察中且过 end_date 的追踪在列表查询时自动置为已到期"""
    _create_tracker(end_offset_days=-3)
    assert DecisionTracker.objects.filter(status='观察中').exists()
    resp = APIClient().get(TRACKERS_URL)
    assert resp.status_code == 200
    assert not DecisionTracker.objects.filter(status='观察中').exists()
    assert DecisionTracker.objects.filter(status='已到期').count() == 1
    # 按状态过滤也能查到（列表为分页格式）
    resp = APIClient().get(TRACKERS_URL, {'status': '已到期'})
    assert resp.data['count'] == 1
    assert resp.data['results'][0]['status'] == '已到期'


@pytest.mark.django_db
def test_report_aggregation() -> None:
    """核心：报告返回倾向统计/月度趋势/理由分组"""
    tracker = _create_tracker()
    _add_record(tracker['id'], 'continue', '稳定双休', days_ago=20)
    _add_record(tracker['id'], 'continue', '同事关系好', days_ago=19)
    _add_record(tracker['id'], 'quit', '需求频繁变更', days_ago=18)
    _add_record(tracker['id'], 'quit', '无效加班多', days_ago=5)  # 可能跨月
    resp = APIClient().get(f'{TRACKERS_URL}{tracker["id"]}/report/')
    assert resp.status_code == 200
    report = resp.data
    assert report['total_records'] == 4
    stats = {s['tendency']: s for s in report['tendency_stats']}
    assert stats['continue']['count'] == 2
    assert stats['quit']['count'] == 2
    assert stats['continue']['percent'] == 50.0
    # 月度趋势按月份升序
    months = [m['month'] for m in report['monthly_trend']]
    assert months == sorted(months)
    assert sum(m['continue'] + m['quit'] + m['uncertain'] for m in report['monthly_trend']) == 4
    # 理由按倾向分组且去空
    assert len(report['reasons']['continue']) == 2
    assert len(report['reasons']['quit']) == 2
    assert all(r['reason'] for r in report['reasons']['continue'])


@pytest.mark.django_db
def test_report_empty_tracker() -> None:
    """边界：零记录报告——计数全 0、趋势空、理由空"""
    tracker = _create_tracker()
    resp = APIClient().get(f'{TRACKERS_URL}{tracker["id"]}/report/')
    report = resp.data
    assert report['total_records'] == 0
    assert report['monthly_trend'] == []
    assert all(v == [] for v in report['reasons'].values())


@pytest.mark.django_db
def test_decide_requires_final_decision() -> None:
    """边界：decide 未填最终决定 → 400"""
    tracker = _create_tracker()
    resp = APIClient().post(f'{TRACKERS_URL}{tracker["id"]}/decide/', {}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_decide_then_archive_flow() -> None:
    """核心：decide 置已决策 + 决定日期；archive 置已归档 + 事后回看"""
    tracker = _create_tracker()
    resp = APIClient().post(f'{TRACKERS_URL}{tracker["id"]}/decide/',
                            {'final_decision': '离职', 'decision_date': '2026-09-01'}, format='json')
    assert resp.status_code == 200
    t = DecisionTracker.objects.get(id=tracker['id'])
    assert t.status == '已决策'
    assert t.final_decision == '离职'
    assert str(t.decision_date) == '2026-09-01'

    resp = APIClient().post(f'{TRACKERS_URL}{tracker["id"]}/archive/',
                            {'review_note': '30 天后看，仍然不后悔'}, format='json')
    assert resp.status_code == 200
    t = DecisionTracker.objects.get(id=tracker['id'])
    assert t.status == '已归档'
    assert t.review_note == '30 天后看，仍然不后悔'


@pytest.mark.django_db
def test_delete_record() -> None:
    """回归：误记的记录可删除"""
    tracker = _create_tracker()
    rec = _add_record(tracker['id'], 'uncertain', '还没想清楚')
    resp = APIClient().delete(f"{RECORDS_URL}{rec['id']}/")
    assert resp.status_code == 204
    assert DecisionRecord.objects.count() == 0
