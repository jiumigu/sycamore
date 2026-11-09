"""产出统计口径（v3.62.39 改造）

守三件事：
1. **窗口是显式参数** —— 以前统计恒按「今年」过滤，界面上没有任何痕迹；
   未填发生日期的记录被 `occurred_at__year=...` 永久排除（实测 23 条只剩 22）。
2. **样本不足不报比例** —— 3 件里 2 件没做成，说「33% 良品率」是自欺。
3. **失败类型分布** —— 这是这一页唯一能指导下一步的东西，口径必须对
   （良品不计入；没填类型的单独计数，不能让它从分母里蒸发）。
"""
import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.goals.models import OutputRecord

LIST = '/api/goals/outputs/'
STATS = '/api/goals/outputs/stats/'


@pytest.fixture
def client():
    return APIClient()


def _rec(quality='good', days_ago=0, fail_type='', category='work', title='事件'):
    occurred = None if days_ago is None else dt.date.today() - dt.timedelta(days=days_ago)
    return OutputRecord.objects.create(
        user_id=1, title=title, quality=quality, category=category,
        fail_type=fail_type, occurred_at=occurred,
    )


# ══════════════════════════════════════════════════════════
# 窗口
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_window_30d_excludes_older(client):
    _rec('good', days_ago=1)
    _rec('good', days_ago=40)
    d = client.get(STATS, {'window': '30d'}).json()
    assert d['window'] == '30d'
    assert d['total_records'] == 1


@pytest.mark.django_db
def test_window_all_includes_undated(client):
    _rec('good', days_ago=200)
    _rec('good', days_ago=None)
    assert client.get(STATS, {'window': 'all'}).json()['total_records'] == 2
    # 30 天口径里两条都不在，但要如实报告「有 1 条未填日期」
    d30 = client.get(STATS, {'window': '30d'}).json()
    assert d30['total_records'] == 0
    assert d30['undated_count'] == 1


@pytest.mark.django_db
def test_unknown_window_falls_back_to_30d(client):
    _rec('good', days_ago=1)
    assert client.get(STATS, {'window': 'bogus'}).json()['window'] == '30d'


# ══════════════════════════════════════════════════════════
# 样本门槛
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_sample_not_enough_below_threshold(client):
    for i in range(4):
        _rec('defective', fail_type='careless', title=f'i{i}')
    d = client.get(STATS, {'window': '30d'}).json()
    assert d['min_sample'] == 5
    assert d['sample_enough'] is False
    assert d['redo_count'] == 4


@pytest.mark.django_db
def test_sample_enough_at_threshold(client):
    for i in range(5):
        _rec('good', title=f'i{i}')
    assert client.get(STATS, {'window': '30d'}).json()['sample_enough'] is True


# ══════════════════════════════════════════════════════════
# 失败类型分布
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_fail_type_counts_and_order(client):
    _rec('defective', fail_type='careless', title='a')
    _rec('waste', fail_type='cognitive', title='b')
    _rec('defective', fail_type='cognitive', title='c')
    _rec('good', fail_type='careless', title='d')  # 良品不计入

    d = client.get(STATS, {'window': '30d'}).json()
    assert d['redo_count'] == 3
    counts = {x['value']: x['count'] for x in d['by_fail_type']}
    assert counts == {'cognitive': 2, 'careless': 1}
    # 排序：次数多的在前
    assert d['by_fail_type'][0]['value'] == 'cognitive'
    assert d['top_fail_type']['label'] == '认知盲区'


@pytest.mark.django_db
def test_fail_type_missing_is_counted(client):
    """没填类型的不能从分母里消失 —— 否则 sum(by_fail_type) < redo_count"""
    _rec('defective', fail_type='', title='a')
    _rec('defective', fail_type='luck', title='b')
    d = client.get(STATS, {'window': '30d'}).json()
    assert d['redo_count'] == 2
    assert d['fail_type_missing'] == 1
    assert sum(x['count'] for x in d['by_fail_type']) + d['fail_type_missing'] == d['redo_count']


@pytest.mark.django_db
def test_no_redo_means_no_top(client):
    _rec('good')
    d = client.get(STATS, {'window': '30d'}).json()
    assert d['redo_count'] == 0
    assert d['top_fail_type'] is None
    assert d['by_fail_type'] == []


# ══════════════════════════════════════════════════════════
# 列表：分页 + 排序
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_list_is_paginated(client):
    for i in range(23):
        _rec('good', days_ago=i, title=f'i{i}')
    d = client.get(LIST, {'window': 'all', 'page': 1, 'page_size': 20}).json()
    assert d['count'] == 23
    assert len(d['results']) == 20
    d2 = client.get(LIST, {'window': 'all', 'page': 2, 'page_size': 20}).json()
    assert len(d2['results']) == 3


@pytest.mark.django_db
def test_list_orders_by_occurred_at(client):
    _rec('good', days_ago=1, title='近')
    _rec('good', days_ago=30, title='远')
    _rec('good', days_ago=None, title='没日期')
    titles = [x['title'] for x in client.get(LIST, {'window': 'all'}).json()['results']]
    # 未填日期的沉底，不顶在最上面
    assert titles == ['近', '远', '没日期']


# ══════════════════════════════════════════════════════════
# 录入：发生日期必填
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_create_requires_occurred_at(client):
    resp = client.post(LIST, {'title': '没写日期', 'quality': 'good', 'category': 'work'}, format='json')
    assert resp.status_code == 400
    assert 'occurred_at' in resp.json()


@pytest.mark.django_db
def test_create_ok_with_occurred_at(client):
    resp = client.post(LIST, {
        'title': '写日期了', 'quality': 'defective', 'category': 'work',
        'fail_type': 'careless', 'occurred_at': str(dt.date.today()),
    }, format='json')
    assert resp.status_code == 201, resp.content[:300]
    assert OutputRecord.objects.count() == 1
