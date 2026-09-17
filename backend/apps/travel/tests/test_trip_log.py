# -*- coding: utf-8 -*-
"""行程日志（打卡聚合 / 沉淀足迹）+ 路线转计划 测试"""
import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.travel.models import TravelRecord, TravelWish

WISHES_URL = '/api/travel/wishes/'
TRIP_LOG_URL = '/api/travel/trip-log/'
CONSOLIDATE_URL = '/api/travel/trip-log/consolidate/'
FROM_ROUTE_URL = '/api/travel/plans/from-route/'
ROUTE_PREVIEW_URL = '/api/travel/plans/route-preview/'


@pytest.fixture
def client():
    return APIClient()


def _visited(name, city, day, category='美食', province='江苏', **extra):
    """造一条已打卡心愿"""
    return TravelWish.objects.create(
        user_id=1, name=name, category=category, city=city, province=province,
        status='已打卡', visited_at=day, **extra,
    )


def _wanted(name, city, category='美食', province='江苏', **extra):
    """造一条「想去」心愿"""
    return TravelWish.objects.create(
        user_id=1, name=name, category=category, city=city, province=province,
        status='想去', **extra,
    )


# ===== 行程日志聚合 =====

def test_trip_log_groups_by_day_and_place(client, db):
    """同一天同城聚合为一天一张卡，按日期倒序"""
    _visited('盐水鸭', '南京', dt.date(2026, 10, 3), visit_rating=5, worth_revisit=True)
    _visited('鸭血粉丝', '南京', dt.date(2026, 10, 3), visit_rating=4)
    _visited('西湖醋鱼', '杭州', dt.date(2026, 10, 4), province='浙江')

    resp = client.get(TRIP_LOG_URL)
    assert resp.status_code == 200
    body = resp.data
    assert body['total_days'] == 2
    assert body['total_items'] == 3
    assert body['pending_days'] == 2

    assert body['days'][0]['city'] == '杭州'
    nanjing = body['days'][1]
    assert nanjing['date'] == '2026-10-03'
    assert nanjing['city'] == '南京'
    assert nanjing['item_count'] == 2
    assert nanjing['worth_count'] == 1
    assert nanjing['avg_rating'] == 4.5
    assert nanjing['consolidated'] is False
    assert '盐水鸭' in nanjing['summary'] and '鸭血粉丝' in nanjing['summary']
    assert nanjing['items'][0]['is_food'] is True


def test_trip_log_merges_city_suffix(client, db):
    """「南京」与「南京市」视为同一天同一个地方"""
    _visited('盐水鸭', '南京', dt.date(2026, 10, 3))
    _visited('鸭血粉丝', '南京市', dt.date(2026, 10, 3))

    body = client.get(TRIP_LOG_URL).data
    assert body['total_days'] == 1
    assert body['days'][0]['item_count'] == 2


def test_trip_log_excludes_unvisited(client, db):
    """仅在「已打卡」且有打卡日期时进入日志"""
    _wanted('没去成的苏州园林', '苏州')
    TravelWish.objects.create(
        user_id=1, name='打卡但无日期', category='景点', city='扬州', status='已打卡',
    )

    body = client.get(TRIP_LOG_URL).data
    assert body['total_days'] == 0
    assert body['total_items'] == 0


def test_trip_log_date_filter(client, db):
    """from / to 过滤；非法日期返回 400"""
    _visited('盐水鸭', '南京', dt.date(2026, 10, 3))
    _visited('西湖醋鱼', '杭州', dt.date(2026, 10, 4), province='浙江')

    body = client.get(TRIP_LOG_URL, {'from': '2026-10-04'}).data
    assert body['total_days'] == 1
    assert body['days'][0]['city'] == '杭州'

    assert client.get(TRIP_LOG_URL, {'from': '2026/10/04'}).status_code == 400


# ===== 沉淀为足迹 =====

def test_consolidate_creates_travel_record(client, db):
    """沉淀：新增一条足迹并回写 visit_record_id，评分取当日均分"""
    w1 = _visited('盐水鸭', '南京', dt.date(2026, 10, 3), visit_rating=5)
    w2 = _visited('鸭血粉丝', '南京', dt.date(2026, 10, 3), visit_rating=5)

    resp = client.post(
        CONSOLIDATE_URL,
        {'date': '2026-10-03', 'city': '南京', 'tcost': 320.5, 'companions': '朋友'},
        format='json',
    )
    assert resp.status_code == 201, resp.data
    record = resp.data['record']
    assert record['tname'] == '南京'
    assert record['tyear'] == 2026
    assert record['ttime'] == '2026-10-03'
    assert record['tcost'] == 320.5
    assert record['rating'] == 5
    assert record['companions'] == '朋友'
    assert resp.data['count'] == 2

    assert TravelRecord.objects.count() == 1
    w1.refresh_from_db()
    w2.refresh_from_db()
    assert w1.visit_record_id == record['tid']
    assert w2.visit_record_id == record['tid']

    # 日志上标记为已沉淀
    day = client.get(TRIP_LOG_URL).data['days'][0]
    assert day['consolidated'] is True
    assert day['record']['tid'] == record['tid']
    assert client.get(TRIP_LOG_URL).data['pending_days'] == 0


def test_consolidate_rejects_empty_day(client, db):
    """该日无待沉淀打卡 → 400；重复沉淀同样被拒"""
    _visited('盐水鸭', '南京', dt.date(2026, 10, 3))
    assert client.post(CONSOLIDATE_URL, {'date': '2026-10-05'}, format='json').status_code == 400

    first = client.post(CONSOLIDATE_URL, {'date': '2026-10-03', 'city': '南京'}, format='json')
    assert first.status_code == 201
    second = client.post(CONSOLIDATE_URL, {'date': '2026-10-03', 'city': '南京'}, format='json')
    assert second.status_code == 400
    assert TravelRecord.objects.count() == 1


def test_consolidate_validates_rating_and_date(client, db):
    """评分越界 / 日期非法 → 400"""
    _visited('盐水鸭', '南京', dt.date(2026, 10, 3))
    resp = client.post(
        CONSOLIDATE_URL, {'date': '2026-10-03', 'city': '南京', 'rating': 9}, format='json',
    )
    assert resp.status_code == 400
    assert client.post(CONSOLIDATE_URL, {'date': '2026/10/03'}, format='json').status_code == 400


# ===== 路线 → 计划 =====

def test_route_preview_matches_city_wishes(client, db):
    """每站返回可带入的城市心愿（兼容市/不带市后缀）"""
    _wanted('盐水鸭', '南京')
    _wanted('鸭血粉丝', '南京市')
    _wanted('西湖醋鱼', '杭州', province='浙江')

    resp = client.post(ROUTE_PREVIEW_URL, {'destinations': ['南京市', '杭州']}, format='json')
    assert resp.status_code == 200
    stations = resp.data['stations']
    assert stations[0]['wish_count'] == 2
    assert stations[1]['wish_count'] == 1
    assert all(w['is_food'] for w in stations[0]['wishes'])


def test_create_plan_from_route_with_wishes(client, db):
    """带心愿生成计划：子项关联心愿、心愿转「已列入计划」、备注记录路线"""
    w1 = _wanted('盐水鸭', '南京')
    w2 = _wanted('中山陵', '南京', category='景点')

    resp = client.post(FROM_ROUTE_URL, {
        'name': '宁杭线',
        'origin': '福州',
        'destinations': ['南京', '杭州'],
        'start_date': '2026-10-01',
        'wish_ids': [w1.id, w2.id],
    }, format='json')
    assert resp.status_code == 201, resp.data
    assert resp.data['name'] == '宁杭线'
    assert resp.data['destination'] == '杭州'
    assert resp.data['start_date'] == '2026-10-01'
    assert '由路线推演生成' in resp.data['notes']
    assert len(resp.data['items']) == 2
    assert {i['wish'] for i in resp.data['items']} == {w1.id, w2.id}

    w1.refresh_from_db()
    w2.refresh_from_db()
    assert w1.status == '已列入计划'
    assert w2.status == '已列入计划'


def test_create_plan_from_route_without_wishes(client, db):
    """不带心愿：每个目的地各生成一条待细化条目"""
    resp = client.post(FROM_ROUTE_URL, {
        'origin': '福州', 'destinations': ['南京', '杭州'],
    }, format='json')
    assert resp.status_code == 201, resp.data
    assert [i['name'] for i in resp.data['items']] == ['南京', '杭州']
    assert all(i['wish'] is None for i in resp.data['items'])
    assert resp.data['name'] == '南京等 2 站'


def test_create_plan_from_route_validates(client, db):
    """缺少目的地 / 日期非法 → 400"""
    assert client.post(FROM_ROUTE_URL, {'origin': '福州'}, format='json').status_code == 400
    resp = client.post(
        FROM_ROUTE_URL, {'destinations': ['南京'], 'start_date': '2026/10/01'}, format='json',
    )
    assert resp.status_code == 400
