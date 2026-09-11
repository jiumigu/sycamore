"""决策追踪器测试 — 状态流转 / 日常记录 / 到期汇总报告 / 随时预览"""
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


def _add_record(tracker_id: int, tendency: str, reason: str = '', days_ago: int = 0,
                intensity: int = 3) -> dict:
    payload = {
        'tracker': tracker_id,
        'record_date': (date.today() - timedelta(days=days_ago)).isoformat(),
        'tendency': tendency,
        'reason': reason,
        'intensity': intensity,
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
    assert rec.intensity == 3
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


@pytest.mark.django_db
def test_preview_weighted_score_matches_manual_calc() -> None:
    """核心：preview 强度加权分数 = 手工计算（强度即权重 1–5）"""
    tracker = _create_tracker()
    _add_record(tracker['id'], 'quit', '需求反复变更', days_ago=2, intensity=5)
    _add_record(tracker['id'], 'quit', '无效加班多', days_ago=1, intensity=1)
    _add_record(tracker['id'], 'continue', '团队氛围好', days_ago=0, intensity=3)

    resp = APIClient().get(f'{TRACKERS_URL}preview/', {'tracker': tracker['id']})
    assert resp.status_code == 200
    item = resp.data['items'][0]
    assert item['total_records'] == 3
    assert item['record_days'] == 3

    # 手工计算：quit 加权 5+1=6，continue 加权 3 → (6-3)/(6+3)*100 = 33.3
    assert item['weighted_total'] == 9
    assert item['weighted_score'] == 33.3
    assert item['weighted_lean_percent'] == 66.7
    # 计数口径：quit 2/3
    assert item['lean_tendency'] == 'quit'
    assert item['lean_label'] == '倾向离开'
    assert item['lean_percent'] == 66.7
    stats = {s['tendency']: s for s in item['tendency_stats']}
    assert stats['quit']['count'] == 2
    assert stats['quit']['weighted'] == 6
    assert stats['quit']['avg_intensity'] == 3.0
    assert stats['quit']['high_count'] == 1  # 只有强度 5 那条算高强度
    assert stats['continue']['weighted'] == 3
    assert stats['uncertain']['count'] == 0
    assert stats['uncertain']['percent'] == 0.0
    assert '其中高强度占 1/2' in item['conclusion']


@pytest.mark.django_db
def test_preview_empty_tracker_returns_zeros() -> None:
    """边界：零记录 preview——计数/占比/加权分全为 0，不虚报倾向"""
    start = date.today()
    resp = APIClient().post(TRACKERS_URL, {
        'topic': '要不要换城市',
        'start_date': start.isoformat(),
        'end_date': (start + timedelta(days=60)).isoformat(),
    }, format='json')
    assert resp.status_code == 201

    resp = APIClient().get(f'{TRACKERS_URL}preview/', {'tracker': resp.data['id']})
    assert resp.status_code == 200
    body = resp.data
    assert body['tracker_count'] == 1
    assert body['total_records'] == 0

    item = body['items'][0]
    assert item['total_records'] == 0
    assert item['record_days'] == 0
    assert item['last_record_date'] is None
    assert item['stale_days'] == 0  # 今天新建，尚未断记
    assert item['needs_reminder'] is False
    assert item['lean_tendency'] is None
    assert item['lean_percent'] == 0.0
    assert item['weighted_total'] == 0
    assert item['weighted_score'] == 0.0
    assert item['weighted_lean_percent'] == 0.0
    assert item['high_count'] == 0
    assert all(
        s['count'] == 0 and s['percent'] == 0.0 and s['weighted'] == 0
        for s in item['tendency_stats']
    )
    assert body['has_reminder'] is False
    assert body['reminder_text'] == ''

    # 同一测试内顺带覆盖断记判定：建了 10 天、一条没记 → 触发提醒（阈值 3 天）
    stale = _create_tracker('要不要换个城市', end_offset_days=60)
    resp = APIClient().get(f'{TRACKERS_URL}preview/', {'tracker': stale['id']})
    stale_item = resp.data['items'][0]
    assert stale_item['total_records'] == 0
    assert stale_item['stale_days'] >= 3
    assert stale_item['needs_reminder'] is True
    assert resp.data['has_reminder'] is True
    assert '没有记录' in resp.data['reminder_text']


@pytest.mark.django_db
def test_custom_lean_options_full_flow() -> None:
    """核心：自定义倾向选项——创建带 lean_options 的追踪，记录直接存选项文字，
    preview/report 按自定义选项统计（含选项文字回显与主导加权优势分）"""
    start = date.today() - timedelta(days=5)
    resp = APIClient().post(TRACKERS_URL, {
        'topic': '眼镜啥时候买',
        'start_date': start.isoformat(),
        'end_date': (date.today() + timedelta(days=30)).isoformat(),
        'lean_options': ['想现在买', '再等等', '不买了'],
    }, format='json')
    assert resp.status_code == 201, resp.data
    assert resp.data['lean_options'] == ['想现在买', '再等等', '不买了']
    tracker_id = resp.data['id']

    # 记录直接用选项文字作 tendency
    _add_record(tracker_id, '想现在买', '磨损影响开车', days_ago=3, intensity=4)
    _add_record(tracker_id, '再等等', '双十一可能降价', days_ago=2, intensity=2)
    _add_record(tracker_id, '想现在买', '看不清很烦', days_ago=1, intensity=3)

    # 预览：主导 = 想现在买（2 条），自定义口径 lean_label 回显选项文字
    resp = APIClient().get(f'{TRACKERS_URL}preview/', {'tracker': tracker_id})
    item = resp.data['items'][0]
    assert item['lean_tendency'] == '想现在买'
    assert item['lean_label'] == '想现在买'
    assert item['lean_percent'] == 66.7
    # 优势分 = (想现在买 7 − 再等等 2) / 9 × 100 = 55.6
    assert item['weighted_score'] == 55.6
    assert item['conclusion'] == '目前 66.7% 倾向「想现在买」，其中高强度占 1/2'
    stats = {s['tendency']: s for s in item['tendency_stats']}
    assert stats['想现在买']['weighted'] == 7
    assert stats['再等等']['count'] == 1
    assert stats['不买了']['count'] == 0
    assert {o['key'] for o in item['options']} == {'想现在买', '再等等', '不买了'}

    # 报告：理由按自定义选项分组
    resp = APIClient().get(f'{TRACKERS_URL}{tracker_id}/report/')
    report = resp.data
    assert {o['key'] for o in report['options']} == {'想现在买', '再等等', '不买了'}
    assert len(report['reasons']['想现在买']) == 2
    assert report['monthly_trend'][0]['想现在买'] == 2

    # 默认三项追踪不受影响（不带 lean_options 建的既有追踪仍可用 continue/quit）
    legacy = _create_tracker()
    _add_record(legacy['id'], 'continue', '稳定', days_ago=0)
    assert APIClient().get(f'{TRACKERS_URL}preview/', {'tracker': legacy['id']}).status_code == 200


@pytest.mark.django_db
def test_record_tendency_must_be_in_tracker_options() -> None:
    """边界：tendency 不在所属追踪的选项内 → 400（默认追踪不收中文，自定义追踪不收 continue）"""
    legacy = _create_tracker()
    payload = {
        'tracker': legacy['id'],
        'record_date': date.today().isoformat(),
        'tendency': '想继续',  # 默认追踪只认 continue/quit/uncertain
        'intensity': 3,
    }
    assert APIClient().post(RECORDS_URL, payload, format='json').status_code == 400

    start = date.today()
    resp = APIClient().post(TRACKERS_URL, {
        'topic': '要不要装充电桩',
        'start_date': start.isoformat(),
        'end_date': (start + timedelta(days=30)).isoformat(),
        'lean_options': ['装', '不装'],
    }, format='json')
    tracker_id = resp.data['id']
    payload = {'tracker': tracker_id, 'record_date': date.today().isoformat(),
               'tendency': 'continue', 'intensity': 3}
    assert APIClient().post(RECORDS_URL, payload, format='json').status_code == 400
    payload['tendency'] = '装'
    assert APIClient().post(RECORDS_URL, payload, format='json').status_code == 201


@pytest.mark.django_db
def test_lean_options_validation() -> None:
    """边界：lean_options 少于 2 项 / 重复 / 空串 → 400；空数组视同用默认"""
    base = {
        'topic': '校验选项',
        'start_date': date.today().isoformat(),
        'end_date': (date.today() + timedelta(days=30)).isoformat(),
    }
    for bad in (['只给一项'], ['重复', '重复'], ['好', '']):
        assert APIClient().post(TRACKERS_URL, {**base, 'lean_options': bad}, format='json').status_code == 400, bad
    resp = APIClient().post(TRACKERS_URL, {**base, 'lean_options': []}, format='json')
    assert resp.status_code == 201
    assert resp.data['lean_options'] is None
