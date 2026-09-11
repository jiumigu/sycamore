# -*- coding: utf-8 -*-
"""旅行心愿单测试 — CRUD / 坐标解析 / 加入计划 / 打卡联动"""
import pytest
from rest_framework.test import APIClient

from apps.travel.models import TravelPlan, TravelPlanItem, TravelWish

WISHES_URL = '/api/travel/wishes/'
PLANS_URL = '/api/travel/plans/'


@pytest.fixture
def client():
    return APIClient()


def _create_wish(client, name='中山陵', category='景点', city='南京', **extra):
    payload = {'name': name, 'category': category, 'city': city, **extra}
    resp = client.post(WISHES_URL, payload, format='json')
    assert resp.status_code == 201, resp.data
    return resp.data


def test_create_wish_ok(client, db):
    """创建心愿：默认状态想去、坐标自动解析（测试库预置一条坐标）"""
    from apps.toolkit.models import CityCoordinate
    CityCoordinate.objects.create(
        name='中山陵', full_name='江苏省南京市中山陵', province='江苏',
        lng=118.85, lat=32.06, city_type='景区',
    )
    data = _create_wish(client)
    assert data['status'] == '想去'
    assert data['province'] == '江苏'
    assert data['lng'] is not None and data['lat'] is not None


def test_create_wish_without_coord_falls_back(client, db):
    """无法解析坐标的心愿：坐标为空但不报错，省份可留空"""
    data = _create_wish(client, name='不存在的虚拟地点xyz', city='')
    assert data['lng'] is None
    assert data['status'] == '想去'


def test_wish_stats(client, db):
    """统计接口按状态/分类聚合"""
    _create_wish(client, name='中山陵')
    _create_wish(client, name='蛋烘糕', category='美食', city='成都')
    resp = client.get(f'{WISHES_URL}stats/')
    assert resp.status_code == 200
    body = resp.data
    assert body['total'] == 2
    assert body['by_status']['想去'] == 2
    assert body['by_category']['美食'] == 1


def test_mark_visited_toggle(client, db):
    """打卡 / 取消打卡 的状态往返"""
    wish = _create_wish(client)
    resp = client.post(f"{WISHES_URL}{wish['id']}/mark_visited/", {}, format='json')
    assert resp.status_code == 200
    assert resp.data['status'] == '已打卡'
    assert resp.data['visited_at'] is not None

    resp = client.post(f"{WISHES_URL}{wish['id']}/mark_visited/", {}, format='json')
    assert resp.data['status'] == '想去'
    assert resp.data['visited_at'] is None


def test_add_to_plan_creates_plan_and_item(client, db):
    """未指定计划时自动新建计划，并生成关联子项、心愿状态转已列入计划"""
    wish = _create_wish(client, name='蛋烘糕', category='美食', city='成都')
    resp = client.post(f"{WISHES_URL}{wish['id']}/add_to_plan/", {}, format='json')
    assert resp.status_code == 200, resp.data
    assert resp.data['plan']['destination'] == '成都'
    assert resp.data['item']['item_type'] == 'food'
    assert resp.data['item']['wish'] == wish['id']

    refreshed = TravelWish.objects.get(id=wish['id'])
    assert refreshed.status == '已列入计划'
    assert TravelPlanItem.objects.filter(wish_id=wish['id']).count() == 1


def test_add_to_existing_plan_and_duplicate_guard(client, db):
    """加入已有计划；重复加入同一计划被拒"""
    plan = TravelPlan.objects.create(user_id=1, name='南京之旅', destination='南京')
    wish = _create_wish(client)
    resp = client.post(f"{WISHES_URL}{wish['id']}/add_to_plan/", {'plan_id': plan.id}, format='json')
    assert resp.status_code == 200
    assert resp.data['item']['item_type'] == 'scenic'

    resp2 = client.post(f"{WISHES_URL}{wish['id']}/add_to_plan/", {'plan_id': plan.id}, format='json')
    assert resp2.status_code == 400
    assert '已在此计划' in resp2.data['error']


def test_toggle_plan_item_syncs_wish(client, db):
    """计划子项打卡 ↔ 心愿状态联动（勾选→已打卡，取消→已列入计划）"""
    plan = TravelPlan.objects.create(user_id=1, name='南京之旅', destination='南京')
    wish = _create_wish(client)
    item = TravelPlanItem.objects.create(
        plan=plan, wish_id=wish['id'], item_type='scenic', name='中山陵',
    )

    resp = client.post(f'{PLANS_URL}{plan.id}/toggle-item/', {'item_id': item.id}, format='json')
    assert resp.status_code == 200
    w = TravelWish.objects.get(id=wish['id'])
    assert w.status == '已打卡' and w.visited_at is not None

    resp = client.post(f'{PLANS_URL}{plan.id}/toggle-item/', {'item_id': item.id}, format='json')
    assert resp.status_code == 200
    w.refresh_from_db()
    assert w.status == '已列入计划' and w.visited_at is None


def test_plan_items_replace_keeps_wish_link(client, db):
    """计划编辑整体替换 items 时，按 类型|名称 复原心愿关联；被移除的心愿回退想去"""
    plan = TravelPlan.objects.create(user_id=1, name='南京之旅', destination='南京')
    wish = _create_wish(client)
    client.post(f"{WISHES_URL}{wish['id']}/add_to_plan/", {'plan_id': plan.id}, format='json')
    assert TravelWish.objects.get(id=wish['id']).status == '已列入计划'

    # 保留同名子项 → 关联复原
    payload = {
        'name': '南京之旅', 'destination': '南京', 'status': '计划中',
        'items': [{'item_type': 'scenic', 'name': '中山陵', 'estimate_cost': 100}],
    }
    resp = client.put(f'{PLANS_URL}{plan.id}/', payload, format='json')
    assert resp.status_code == 200, resp.data
    assert TravelPlanItem.objects.filter(wish_id=wish['id']).count() == 1

    # 移除该子项 → 心愿回退为想去
    payload['items'] = [{'item_type': 'hotel', 'name': '某酒店', 'estimate_cost': 200}]
    resp = client.put(f'{PLANS_URL}{plan.id}/', payload, format='json')
    assert resp.status_code == 200
    assert TravelPlanItem.objects.filter(wish_id=wish['id']).count() == 0
    assert TravelWish.objects.get(id=wish['id']).status == '想去'


def test_wish_filter_by_status_and_category(client, db):
    """列表接口支持 状态/分类/搜索 过滤"""
    _create_wish(client, name='中山陵')
    _create_wish(client, name='蛋烘糕', category='美食', city='成都')
    resp = client.get(WISHES_URL, {'category': '美食'})
    assert len(resp.data) == 1 and resp.data[0]['name'] == '蛋烘糕'
    resp = client.get(WISHES_URL, {'search': '中山'})
    assert len(resp.data) == 1 and resp.data[0]['name'] == '中山陵'
