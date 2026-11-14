"""旅行路线「站点层」的接口契约（Step 2）

对应设计稿 §8 的验收判据：三层金额恒等式、`days=null`、未定位城市、
删站不级联、重排必须整份给、条目挪站只改归属不改总额。

这组测试钉的是**接口出参**，不是内部函数 —— 前端只认这份 JSON。
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.travel.models import TravelPlan, TravelPlanItem, TravelPlanStop
from apps.travel.services import TravelPlanService

PLANS = '/api/travel/plans/'


def _route(name='闽粤沿海线', start=date(2026, 12, 1)):
    """宁德 → 泉州(2 天) → 潮州(待定) → 广州(1 天)，外加两段城际交通

    金额故意带小数与「不整」的分布，避免四舍五入把错误抹平：
        泉州 80.50 + 29.50 = 110.00、潮州 60.00、广州 0（没录）
        城际 120.00 + 180.00 = 300.00
    """
    plan = TravelPlan.objects.create(
        user_id=1, name=name, destination='', start_date=start, status='计划中',
    )
    quanzhou = TravelPlanStop.objects.create(plan=plan, city='泉州', province='福建省', order=1, days=2)
    chaozhou = TravelPlanStop.objects.create(plan=plan, city='潮州', order=2)
    guangzhou = TravelPlanStop.objects.create(plan=plan, city='广州', order=3, days=1)

    TravelPlanItem.objects.create(plan=plan, stop=quanzhou, item_type='food', name='牛肉清汤粉', estimate_cost=Decimal('80.50'))
    TravelPlanItem.objects.create(plan=plan, stop=quanzhou, item_type='scenic', name='开元寺', estimate_cost=Decimal('29.50'))
    TravelPlanItem.objects.create(plan=plan, stop=chaozhou, item_type='food', name='牛肉火锅', estimate_cost=Decimal('60'))
    TravelPlanItem.objects.create(plan=plan, item_type='transport', name='宁德→泉州 高铁', estimate_cost=Decimal('120'))
    TravelPlanItem.objects.create(plan=plan, item_type='transport', name='潮州→广州 高铁', estimate_cost=Decimal('180'))

    TravelPlanService.recalculate_total(plan)
    plan.refresh_from_db()
    return plan, quanzhou, chaozhou, guangzhou


@pytest.fixture
def route():
    return _route()


# ── 三层读 ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_detail_splits_three_layers(route):
    """计划详情按三层下发：站 / 路上 / 合计，且恒等式成立。"""
    plan, quanzhou, chaozhou, guangzhou = route
    data = APIClient().get(f'{PLANS}{plan.pk}/').data

    assert [s['city_input'] for s in data['stops']] == ['泉州', '潮州', '广州']
    assert [s['subtotal'] for s in data['stops']] == [110.0, 60.0, 0.0]

    # 城际交通不混进任何城市
    assert [i['name'] for i in data['transfer_items']] == ['宁德→泉州 高铁', '潮州→广州 高铁']
    assert data['transfer_total'] == 300.0

    # 🔴 恒等式：Σ各站 + 路上 = 总额（按定义必成立，不依赖造数巧合）
    assert data['stops_total'] == 170.0
    assert data['stops_total'] + data['transfer_total'] == data['total_estimate'] == 470.0

    # 金额出参必须是 number：前端 formatAmount 遇字符串会渲染成 ¥—
    for key in ('total_estimate', 'stops_total', 'transfer_total'):
        assert isinstance(data[key], float), key
    assert all(isinstance(s['subtotal'], float) for s in data['stops'])


@pytest.mark.django_db
def test_grouped_subtotals_match_per_stop_sum(route):
    """分组求和（一次查询）与逐站求和必须一致 —— 两处聚合不许分叉。"""
    plan, quanzhou, chaozhou, guangzhou = route
    grouped = TravelPlanService.subtotals(plan)
    for stop in (quanzhou, chaozhou, guangzhou):
        assert grouped.get(stop.pk, Decimal('0')) == TravelPlanService.stop_subtotal(stop)


@pytest.mark.django_db
def test_list_omits_items_but_keeps_stops(route):
    """列表页带站点（要画路线串），但**不展开条目** —— 键整个不出现，不是空数组。"""
    plan, *_ = route
    rows = APIClient().get(PLANS).data
    rows = rows['results'] if isinstance(rows, dict) else rows

    target = next(r for r in rows if r['id'] == plan.pk)
    assert [s['city_input'] for s in target['stops']] == ['泉州', '潮州', '广州']
    assert 'items' not in target['stops'][0]
    assert target['stops_total'] == 170.0


@pytest.mark.django_db
def test_detail_includes_stop_items(route):
    plan, quanzhou, *_ = route
    data = APIClient().get(f'{PLANS}{plan.pk}/').data
    first = data['stops'][0]
    assert {i['name'] for i in first['items']} == {'牛肉清汤粉', '开元寺'}
    assert all(i['stop'] == quanzhou.pk for i in first['items'])


# ── null ≠ 0 ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_days_null_makes_total_days_unknown(route):
    """任一站天数未知 ⇒ 全程天数 `null`（不是 0，也不是「已知部分之和」）。"""
    plan, quanzhou, chaozhou, guangzhou = route
    data = APIClient().get(f'{PLANS}{plan.pk}/').data
    assert data['total_days'] is None

    TravelPlanStop.objects.filter(pk=chaozhou.pk).update(days=1)
    data = APIClient().get(f'{PLANS}{plan.pk}/').data
    assert data['total_days'] == 4  # 2 + 1 + 1


@pytest.mark.django_db
def test_arrive_date_stops_at_unknown_days(route):
    """到达日期：本站算得出就给自己，后面的站算不出就给 null（不拿 0 顶替）。"""
    plan, *_ = route
    data = APIClient().get(f'{PLANS}{plan.pk}/').data
    dates = [s['arrive_date'] for s in data['stops']]
    # 泉州 12-01 到，2 天 ⇒ 潮州 12-03；潮州天数未知 ⇒ 广州算不出
    assert dates == ['2026-12-01', '2026-12-03', None]


# ── 站点写操作 ───────────────────────────────────────────────

@pytest.mark.django_db
def test_add_stop_appends_and_returns_payload(route):
    plan, *_ = route
    resp = APIClient().post(f'{PLANS}{plan.pk}/stops/', {'city': '深圳', 'days': 2}, format='json')

    assert resp.status_code == 201
    assert resp.data['order'] == 4
    assert resp.data['subtotal'] == 0.0
    assert resp.data['located'] is True
    assert resp.data['city'] == '深圳市'  # 规范名
    assert resp.data['city_input'] == '深圳'
    assert resp.data['items'] == []


@pytest.mark.django_db
def test_add_stop_rejects_blank_city(route):
    plan, *_ = route
    resp = APIClient().post(f'{PLANS}{plan.pk}/stops/', {'city': '   '}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_patch_days_recomputes_arrive_dates(route):
    plan, quanzhou, chaozhou, guangzhou = route
    resp = APIClient().patch(
        f'{PLANS}{plan.pk}/stops/{quanzhou.pk}/', {'days': 3}, format='json',
    )
    assert resp.status_code == 200

    data = APIClient().get(f'{PLANS}{plan.pk}/').data
    assert [s['arrive_date'] for s in data['stops']] == ['2026-12-01', '2026-12-04', None]


@pytest.mark.django_db
def test_patch_city_updates_derived_destination(route):
    """`destination` 是派生的：改最后一站的城市，它必须跟着变。"""
    plan, quanzhou, chaozhou, guangzhou = route
    assert plan.destination == '广州'

    APIClient().patch(f'{PLANS}{plan.pk}/stops/{guangzhou.pk}/', {'city': '佛山'}, format='json')
    plan.refresh_from_db()
    assert plan.destination == '佛山'


@pytest.mark.django_db
def test_delete_stop_with_items_is_blocked(route):
    """删站有条目 ⇒ 400 且列出挡路的条目，**一条都不删**。"""
    plan, quanzhou, *_ = route
    resp = APIClient().delete(f'{PLANS}{plan.pk}/stops/{quanzhou.pk}/')

    assert resp.status_code == 400
    assert '2 条' in resp.data['error']
    assert {b['name'] for b in resp.data['blocking']} == {'牛肉清汤粉', '开元寺'}
    assert TravelPlanItem.objects.filter(stop=quanzhou).count() == 2


@pytest.mark.django_db
def test_delete_empty_stop_recomputes_total(route):
    plan, quanzhou, chaozhou, guangzhou = route
    before = plan.total_estimate

    resp = APIClient().delete(f'{PLANS}{plan.pk}/stops/{guangzhou.pk}/')
    assert resp.status_code == 204

    plan.refresh_from_db()
    assert plan.total_estimate == before  # 空站没金额，删了总额不变
    assert plan.destination == '潮州'  # 末站变了，派生值跟着回退


@pytest.mark.django_db
def test_reorder_only_touches_order(route):
    plan, quanzhou, chaozhou, guangzhou = route
    before = APIClient().get(f'{PLANS}{plan.pk}/').data

    ids = [guangzhou.pk, quanzhou.pk, chaozhou.pk]
    resp = APIClient().post(f'{PLANS}{plan.pk}/stops/reorder/', {'order': ids}, format='json')
    assert resp.status_code == 200
    assert [s['id'] for s in resp.data['stops']] == ids
    assert [s['order'] for s in resp.data['stops']] == [1, 2, 3]

    after = APIClient().get(f'{PLANS}{plan.pk}/').data
    assert after['total_estimate'] == before['total_estimate']
    # 每个条目的归属站没动（只是站的顺序变了）
    by_id = {s['id']: s for s in after['stops']}
    assert {i['name'] for i in by_id[quanzhou.pk]['items']} == {'牛肉清汤粉', '开元寺'}
    assert by_id[guangzhou.pk]['items'] == []
    # 首尾互换 ⇒ 派生的 destination 跟着变
    assert after['destination'] == '潮州'


@pytest.mark.django_db
def test_reorder_requires_full_id_list(route):
    """只给一半 id ⇒ 400（否则留下 1,3,7 这种空洞顺序，下一站又得猜）。"""
    plan, quanzhou, *_ = route
    resp = APIClient().post(
        f'{PLANS}{plan.pk}/stops/reorder/', {'order': [quanzhou.pk]}, format='json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_reorder_rejects_bad_payload(route):
    plan, *_ = route
    api = APIClient()
    assert api.post(f'{PLANS}{plan.pk}/stops/reorder/', {}, format='json').status_code == 400
    assert api.post(
        f'{PLANS}{plan.pk}/stops/reorder/', {'order': ['a']}, format='json',
    ).status_code == 400


# ── 条目挪站 ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_move_item_changes_attribution_not_total(route):
    """把「牛肉清汤粉」从泉州挪到潮州：两站合计此消彼长，总额不变。"""
    plan, quanzhou, chaozhou, _ = route
    item = plan.items.get(name='牛肉清汤粉')

    resp = APIClient().post(
        f'{PLANS}{plan.pk}/items/{item.pk}/move/', {'stop': chaozhou.pk}, format='json',
    )
    assert resp.status_code == 200
    assert resp.data['stop'] == chaozhou.pk

    data = APIClient().get(f'{PLANS}{plan.pk}/').data
    subs = {s['city_input']: s['subtotal'] for s in data['stops']}
    assert subs == {'泉州': 29.5, '潮州': 140.5, '广州': 0.0}
    assert data['total_estimate'] == 470.0


# ── 删计划 ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_delete_plan_with_stops_and_items(route):
    """删整条计划必须能删掉。

    🔴 `TravelPlanItem.stop` 是 PROTECT（删**站**时不许连带删预算），
       而 Django 的 ProtectedError 会连「删整条计划」一起挡下来 ——
       不显式按序删就是 500，且只有「有站且站下有条目」时才复现。
    """
    plan, *_ = route
    resp = APIClient().delete(f'{PLANS}{plan.pk}/')

    assert resp.status_code == 204
    assert not TravelPlan.objects.filter(pk=plan.pk).exists()
    assert not TravelPlanStop.objects.filter(plan_id=plan.pk).exists()
    assert not TravelPlanItem.objects.filter(plan_id=plan.pk).exists()


# ── 建计划（单站特例）────────────────────────────────────────

@pytest.mark.django_db
def test_create_plan_with_destination_makes_one_stop():
    """老弹窗只填一个目的地 ⇒ 计划就是「一站路线」，条目默认归这一站。"""
    data = APIClient().post(
        PLANS,
        {
            'name': '龙岩 3 日', 'destination': '龙岩', 'start_date': '2026-10-01',
            'items': [
                {'item_type': 'food', 'name': '簸箕饭', 'estimate_cost': 15},
                {'item_type': 'transport', 'name': '来回', 'estimate_cost': 600},
            ],
        },
        format='json',
    ).data

    assert len(data['stops']) == 1
    assert data['stops'][0]['city_input'] == '龙岩'
    assert len(data['stops'][0]['items']) == 2
    assert data['transfer_items'] == []  # 一条都不许漏到「路上」
    assert data['stops_total'] == 615.0


@pytest.mark.django_db
def test_create_plan_with_stops_builds_the_whole_route():
    """新建时就带整条路线：站点按数组顺序落地，条目用 `stop_index` 指认归属。

    `stop_index` 存在的唯一理由：新建那一刻站点 id 还不存在，前端没法用 id 指认。
    """
    data = APIClient().post(
        PLANS,
        {
            'name': '闽粤沿海线', 'start_date': '2026-12-01',
            'stops': [
                {'city': '泉州', 'days': 2},
                {'city': '潮州'},
                {'city': '广州', 'days': 1},
            ],
            'items': [
                {'item_type': 'food', 'name': '牛肉清汤粉', 'estimate_cost': 30, 'stop_index': 0},
                {'item_type': 'food', 'name': '牛肉火锅', 'estimate_cost': 60, 'stop_index': 1},
                {'item_type': 'transport', 'name': '宁德→泉州 高铁', 'estimate_cost': 120},
            ],
        },
        format='json',
    ).data

    assert [s['city_input'] for s in data['stops']] == ['泉州', '潮州', '广州']
    assert [s['order'] for s in data['stops']] == [1, 2, 3]
    # 条目按 stop_index 落站，未给下标的进「路上」
    assert [len(s['items']) for s in data['stops']] == [1, 1, 0]
    assert [i['name'] for i in data['transfer_items']] == ['宁德→泉州 高铁']
    # 三层恒等式
    assert data['stops_total'] == 90.0
    assert data['transfer_total'] == 120.0
    assert data['total_estimate'] == 210.0
    # 天数：全给了才是 3；`destination` 派生成末站
    assert data['total_days'] is None  # 潮州没填天数 ⇒ 算不出来，不许当 0 加
    assert data['destination'] == '广州'


@pytest.mark.django_db
def test_create_with_both_stops_and_destination_prefers_stops():
    """`destination` 已转只读派生：同时给时以 `stops` 为准，不许两边各建一站。"""
    data = APIClient().post(
        PLANS,
        {'name': 'x', 'destination': '厦门', 'stops': [{'city': '泉州'}, {'city': '广州'}]},
        format='json',
    ).data

    assert [s['city_input'] for s in data['stops']] == ['泉州', '广州']
    assert data['destination'] == '广州'  # 不是提交的「厦门」


@pytest.mark.django_db
def test_create_rolls_back_plan_when_stop_is_invalid():
    """站点校验失败 ⇒ 整条请求回滚：不能留下一条「0 站 0 元」的空计划。"""
    before = TravelPlan.objects.count()
    resp = APIClient().post(
        PLANS,
        {'name': '半截路线', 'stops': [{'city': '泉州'}, {'city': '  '}]},
        format='json',
    )

    assert resp.status_code == 400
    assert TravelPlan.objects.count() == before
    assert not TravelPlan.objects.filter(name='半截路线').exists()


@pytest.mark.django_db
def test_create_rejects_stop_index_out_of_range():
    """`stop_index` 越界 ⇒ 400，不许静默落到「路上」（钱会跑到城际交通里）。"""
    resp = APIClient().post(
        PLANS,
        {
            'name': 'x', 'stops': [{'city': '泉州'}],
            'items': [{'item_type': 'food', 'name': 'a', 'estimate_cost': 1, 'stop_index': 3}],
        },
        format='json',
    )
    assert resp.status_code == 400
    assert not TravelPlan.objects.filter(name='x').exists()


@pytest.mark.django_db
def test_post_item_defaults_to_sole_stop():
    """单站计划里加条目不写 stop ⇒ 归那一站（显式传 null 才进「路上」）。"""
    plan = TravelPlan.objects.create(user_id=1, name='单站', destination='')
    TravelPlanStop.objects.create(plan=plan, city='龙岩', order=1)

    resp = APIClient().post(
        f'{PLANS}{plan.pk}/items/', {'item_type': 'food', 'name': '簸箕饭', 'estimate_cost': 15},
        format='json',
    )
    assert resp.status_code == 201
    assert resp.data['stop'] is not None


@pytest.mark.django_db
def test_move_item_to_transfer_needs_explicit_null(route):
    """挪到路上必须**显式传 null**：少传一个键不能悄悄把条目从城市里摘走。"""
    plan, quanzhou, *_ = route
    item = plan.items.get(name='开元寺')
    url = f'{PLANS}{plan.pk}/items/{item.pk}/move/'

    assert APIClient().post(url, {}, format='json').status_code == 400

    resp = APIClient().post(url, {'stop': None}, format='json')
    assert resp.status_code == 200
    assert resp.data['stop'] is None

    data = APIClient().get(f'{PLANS}{plan.pk}/').data
    assert data['transfer_total'] == 329.5


@pytest.mark.django_db
def test_move_rejects_stop_from_another_plan(route):
    """跨计划的站点 id ⇒ 400：否则条目会挂到别人家的路线上，界面上看不出来。"""
    plan, *_ = route
    other = _route('别的路线')
    foreign_stop = TravelPlanStop.objects.filter(plan=other[0]).first()
    item = plan.items.get(name='开元寺')

    resp = APIClient().post(
        f'{PLANS}{plan.pk}/items/{item.pk}/move/', {'stop': foreign_stop.pk}, format='json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_post_item_with_stop(route):
    plan, quanzhou, *_ = route
    resp = APIClient().post(
        f'{PLANS}{plan.pk}/items/',
        {'item_type': 'food', 'name': '四果汤', 'estimate_cost': 12, 'stop': quanzhou.pk},
        format='json',
    )
    assert resp.status_code == 201
    assert resp.data['stop'] == quanzhou.pk
    assert resp.data['estimate_cost'] == 12.0

    plan.refresh_from_db()
    assert plan.total_estimate == Decimal('482.00')


@pytest.mark.django_db
def test_unknown_item_key_is_rejected_not_ignored(route):
    """字段名写错不许静默丢弃 —— 那会变成「保存成功但没写进去」。"""
    plan, *_ = route
    resp = APIClient().put(
        f'{PLANS}{plan.pk}/',
        {
            'name': plan.name, 'destination': plan.destination, 'status': plan.status,
            'items': [{'item_type': 'food', 'name': 'x', 'estimate': 10}],
        },
        format='json',
    )
    assert resp.status_code == 400
    assert 'estimate' in str(resp.data)


# ── 由路线推演生成 ───────────────────────────────────────────

@pytest.mark.django_db
def test_from_route_creates_ordered_stops():
    plan_data = APIClient().post(
        f'{PLANS}from-route/',
        {'destinations': ['泉州', '潮州', '广州'], 'start_date': '2026-12-01'},
        format='json',
    ).data

    stops = plan_data['stops']
    assert [s['city_input'] for s in stops] == ['泉州', '潮州', '广州']
    assert [s['order'] for s in stops] == [1, 2, 3]
    # 推演阶段还不知道每站待几天 ⇒ null，不猜
    assert [s['days'] for s in stops] == [None, None, None]
    # 未选心愿时每站一条占位项，落在自己的站下
    assert all(len(s['items']) == 1 for s in stops)
    assert plan_data['total_days'] is None
    assert plan_data['destination'] == '广州'


@pytest.mark.django_db
def test_from_route_attaches_wishes_to_their_stop():
    """心愿按自己的城市落站；对不上站的照样进计划（stop=null）并回给前端。"""
    from apps.travel.models import TravelWish

    w1 = TravelWish.objects.create(user_id=1, name='面线糊', category='美食', province='福建省', city='泉州')
    w2 = TravelWish.objects.create(user_id=1, name='不该出现的城市', category='景点', province='浙江省', city='杭州')

    data = APIClient().post(
        f'{PLANS}from-route/',
        {'destinations': ['泉州', '广州'], 'wish_ids': [w1.id, w2.id]},
        format='json',
    ).data

    by_city = {s['city_input']: s for s in data['stops']}
    assert [i['name'] for i in by_city['泉州']['items']] == ['面线糊']
    # 杭州不在路线里 ⇒ 不落站，但**不丢**：进 transfer_items，并显式回一句
    assert [i['name'] for i in data['transfer_items']] == ['不该出现的城市']
    assert [u['name'] for u in data['unmatched_wishes']] == ['不该出现的城市']

    w1.refresh_from_db()
    assert w1.status == '已列入计划'


@pytest.mark.django_db
def test_route_preview_flags_unlocatable_city():
    rows = APIClient().post(
        f'{PLANS}route-preview/', {'destinations': ['泉州', '不存在测试城']}, format='json',
    ).data['stations']
    assert [r['located'] for r in rows] == [True, False]
