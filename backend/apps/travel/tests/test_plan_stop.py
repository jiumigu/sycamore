"""旅行计划「站点」层 —— 迁移搬迁、三层金额、顺序、到达日期

背景（2026-11-11）：一条出行路线是「宁德 → 泉州 → 漳州 → 潮州 → 广州」这样**多个城市**，
而原来一个 `TravelPlan` 只装得下一个 `destination` 字符串、条目也平铺在计划下，
于是「泉州这一站花多少」答不出来，路线顺序只能塞进 `notes` 由前端正则反解。

这组测试守四件事：
1. **迁移无损**：老计划搬成「一站路线」后，条目一条不少、总额一分不差、可重复跑；
2. **三层金额**：本站合计 / 城际交通 / 计划总额的恒等式；
3. **顺序**：重排只动 `order`，不动条目归属与金额；只给一半 id 必须报错；
4. **`null` ≠ `0`**：`days` 未知时到达日期算不出来，不许拿 0 顶替。
"""
import importlib
from datetime import date
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.db.models.deletion import ProtectedError
from rest_framework.test import APIClient

from apps.travel.models import TravelPlan, TravelPlanItem, TravelPlanStop
from apps.travel.services import TravelPlanService

MIGRATION = importlib.import_module(
    'apps.travel.migrations.0010_travelplanstop_travelplanitem_stop_and_more',
)


def _legacy_plan(name='出发龙岩3日游', destination='龙岩', start=date(2026, 10, 1)):
    """造一条**迁移前形态**的计划：没有站点，条目平铺"""
    plan = TravelPlan.objects.create(
        user_id=1, name=name, destination=destination, start_date=start,
        total_estimate=Decimal('1305.00'),
    )
    TravelPlanItem.objects.create(plan=plan, item_type='food', name='簸箕饭', estimate_cost=Decimal('15'))
    TravelPlanItem.objects.create(plan=plan, item_type='food', name='牛肉清汤粉', estimate_cost=Decimal('30'))
    TravelPlanItem.objects.create(plan=plan, item_type='hotel', name='2晚', estimate_cost=Decimal('360'))
    TravelPlanItem.objects.create(plan=plan, item_type='transport', name='来回', estimate_cost=Decimal('600'))
    return plan


# ── 迁移 ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_backfill_makes_one_stop_and_attaches_every_item():
    """老计划 → 一站路线：条目全部挂上，总额与条数一个都不变。"""
    plan = _legacy_plan()
    MIGRATION.backfill_stops(django_apps, None)

    stops = list(plan.stops.all())
    assert len(stops) == 1
    stop = stops[0]
    assert (stop.city, stop.order, stop.province) == ('龙岩', 1, '')
    # 🔴 天数未知就是 None，不猜 0（老数据里没有任何天数信息）
    assert stop.days is None
    # 条目一条不少，且全部属于这一站
    assert stop.items.count() == 4
    assert plan.items.filter(stop__isnull=True).count() == 0
    # 总额一分不差：迁移只搬归属，不做任何重算
    plan.refresh_from_db()
    assert plan.total_estimate == Decimal('1305.00')


@pytest.mark.django_db
def test_backfill_is_idempotent():
    """重复跑迁移不会凭空多出第二站。"""
    plan = _legacy_plan()
    MIGRATION.backfill_stops(django_apps, None)
    MIGRATION.backfill_stops(django_apps, None)
    assert plan.stops.count() == 1


@pytest.mark.django_db
def test_backfill_skips_plan_without_destination():
    """空计划（没目的地）不造空站点 —— 造了就是一条「未命名」的假路线。"""
    plan = TravelPlan.objects.create(user_id=1, name='草稿', destination='')
    MIGRATION.backfill_stops(django_apps, None)
    assert plan.stops.count() == 0


@pytest.mark.django_db
def test_backfill_does_not_guess_transfer_items():
    """名字像「来回」的交通条目也挂到站上 —— 不按名字猜城际交通（猜错就是悄悄挪钱）。"""
    plan = _legacy_plan()
    MIGRATION.backfill_stops(django_apps, None)
    assert plan.items.get(name='来回').stop_id is not None


@pytest.mark.django_db
def test_unbackfill_detaches_items_without_losing_them():
    """反向：站点拆掉、条目回到未分配，但条目本身还在。"""
    plan = _legacy_plan()
    MIGRATION.backfill_stops(django_apps, None)
    MIGRATION.unbackfill_stops(django_apps, None)

    assert TravelPlanStop.objects.filter(plan=plan).count() == 0
    assert plan.items.count() == 4
    assert plan.items.filter(stop__isnull=True).count() == 4


# ── 三层金额 ──────────────────────────────────────────────────

@pytest.fixture
def route(db):
    """一条 3 站路线 + 1 条城际交通"""
    plan = TravelPlan.objects.create(
        user_id=1, name='闽粤沿海线', destination='', start_date=date(2026, 12, 1),
        total_estimate=Decimal('0'),
    )
    quanzhou = TravelPlanService.add_stop(plan, '泉州', province='福建省', days=2)
    chaozhou = TravelPlanService.add_stop(plan, '潮州', province='广东省', days=1)
    guangzhou = TravelPlanService.add_stop(plan, '广州', province='广东省', days=3)
    TravelPlanItem.objects.create(plan=plan, stop=quanzhou, item_type='food', name='牛肉清汤粉', estimate_cost=Decimal('30'))
    TravelPlanItem.objects.create(plan=plan, stop=quanzhou, item_type='scenic', name='开元寺', estimate_cost=Decimal('50'))
    TravelPlanItem.objects.create(plan=plan, stop=chaozhou, item_type='food', name='牛肉丸', estimate_cost=Decimal('60'))
    TravelPlanItem.objects.create(plan=plan, item_type='transport', name='宁德→泉州 高铁', estimate_cost=Decimal('120'))
    TravelPlanItem.objects.create(plan=plan, item_type='transport', name='潮州→广州 高铁', estimate_cost=Decimal('180'))
    # 走接口时由视图负责重算总额；这里直接写 ORM，必须自己补上这一步，
    # 否则 fixture 造出来的计划总额是 0，断言会把「测试造数漏了」当成「代码算错了」
    TravelPlanService.recalculate_total(plan)
    return plan, quanzhou, chaozhou, guangzhou


@pytest.mark.django_db
def test_totals_identity_holds(route):
    """恒等式：Σ 各站合计 + 城际交通 == 计划总额（按定义必成立的那一条）。"""
    plan, *_ = route
    totals = TravelPlanService.totals(plan)
    assert totals['stops_total'] == Decimal('140.00')
    assert totals['transfer_total'] == Decimal('300.00')
    assert totals['total'] == totals['stops_total'] + totals['transfer_total'] == Decimal('440.00')

    plan.refresh_from_db()
    assert plan.total_estimate == Decimal('440.00')


@pytest.mark.django_db
def test_transfer_items_never_leak_into_stop_subtotal(route):
    """城际交通不计入任何城市 —— 否则「泉州花多少」会掺进宁德→泉州的车票。"""
    plan, quanzhou, chaozhou, _ = route
    assert TravelPlanService.stop_subtotal(quanzhou) == Decimal('80.00')
    assert TravelPlanService.stop_subtotal(chaozhou) == Decimal('60.00')


@pytest.mark.django_db
def test_empty_stop_subtotal_is_zero(route):
    """没有条目的站点合计是 0（不是 None）—— 前端要显示 ¥0，不是「—」。"""
    plan, _, _, guangzhou = route
    assert TravelPlanService.stop_subtotal(guangzhou) == Decimal('0')


# ── 顺序 ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_reorder_only_changes_order(route):
    """重排只动 `order`：条目仍挂在原站、金额一分不变、destination 跟到新末站。"""
    plan, quanzhou, chaozhou, guangzhou = route
    TravelPlanService.reorder_stops(plan, [guangzhou.pk, quanzhou.pk, chaozhou.pk])

    assert [s.city for s in plan.stops.order_by('order')] == ['广州', '泉州', '潮州']
    assert [s.order for s in plan.stops.order_by('order')] == [1, 2, 3]
    assert TravelPlanService.stop_subtotal(quanzhou) == Decimal('80.00')
    plan.refresh_from_db()
    assert plan.total_estimate == Decimal('440.00')
    assert plan.destination == '潮州'


@pytest.mark.django_db
def test_reorder_rejects_partial_list(route):
    """只给一半 id ⇒ 报错，不许留下 1,3 这种空洞顺序。"""
    plan, quanzhou, _, _ = route
    with pytest.raises(ValueError):
        TravelPlanService.reorder_stops(plan, [quanzhou.pk])


@pytest.mark.django_db
def test_add_stop_appends_at_end(route):
    plan, *_ = route
    stop = TravelPlanService.add_stop(plan, '汕头', days=1)
    assert stop.order == 4


# ── 到达日期（null ≠ 0）───────────────────────────────────────

@pytest.mark.django_db
def test_arrive_dates_accumulate_days(route):
    """第一站 = 出发日，之后按天数累加。"""
    plan, quanzhou, chaozhou, guangzhou = route
    dates = TravelPlanService.arrive_dates(plan)
    assert dates[quanzhou.pk] == date(2026, 12, 1)
    assert dates[chaozhou.pk] == date(2026, 12, 3)
    assert dates[guangzhou.pk] == date(2026, 12, 4)


@pytest.mark.django_db
def test_unknown_days_makes_later_dates_unknown(route):
    """某站天数未知 ⇒ 它自己的到达日仍算得出，之后的全部「算不出来」（None）。

    🔴 不许用 0 顶替：把「还不知道」当成「当天走」，行程会凭空少几天。
    """
    plan, quanzhou, chaozhou, guangzhou = route
    TravelPlanStop.objects.filter(pk=quanzhou.pk).update(days=None)

    dates = TravelPlanService.arrive_dates(plan)
    assert dates[quanzhou.pk] == date(2026, 12, 1)
    assert dates[chaozhou.pk] is None
    assert dates[guangzhou.pk] is None


@pytest.mark.django_db
def test_no_start_date_means_no_arrive_dates(route):
    """没填出发日期 ⇒ 全部 None（不假装今天是出发日）。"""
    plan, *_ = route
    TravelPlan.objects.filter(pk=plan.pk).update(start_date=None)
    plan.refresh_from_db()
    assert all(v is None for v in TravelPlanService.arrive_dates(plan).values())


# ── 删除保护 ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_stop_with_items_cannot_be_deleted(route):
    """站下有条目时删站 ⇒ ProtectedError。

    🔴 刻意用 PROTECT 而不是 SET_NULL：SET_NULL 会让被删站点的条目**静默变成
       城际交通**，金额还在、归属错了，最难查；CASCADE 则是把用户手录的预算一起删。
    """
    plan, quanzhou, *_ = route
    with pytest.raises(ProtectedError):
        quanzhou.delete()
    assert TravelPlanStop.objects.filter(pk=quanzhou.pk).exists()


# ── 定位 ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_stop_payload_reports_located_and_subtotal(route):
    """站点出参：规范名 + 坐标 + 本站合计 + 四类计数（全在出参里现算）"""
    plan, quanzhou, *_ = route
    resp = APIClient().get(f'/api/travel/plans/{plan.pk}/')
    assert resp.status_code == 200

    rows = {row['city_input']: row for row in resp.data['stops']}
    assert rows['泉州']['located'] is True
    assert rows['泉州']['subtotal'] == 80.0
    assert rows['泉州']['counts']['food'] == 1
    assert rows['泉州']['counts']['scenic'] == 1
    assert rows['泉州']['days'] == 2
    # 规范名来自坐标表（「泉州」→「泉州市」），原样输入另存 city_input 不丢
    assert rows['泉州']['city'] == '泉州市'


@pytest.mark.django_db
def test_unlocatable_city_is_flagged_not_dropped():
    """定位不到的城市**照样列出来**，只是 `located=False`（不猜坐标、不上图）。"""
    plan = TravelPlan.objects.create(user_id=1, name='测试', destination='')
    TravelPlanService.add_stop(plan, '不存在测试城')

    resp = APIClient().get(f'/api/travel/plans/{plan.pk}/')
    rows = resp.data['stops']
    assert len(rows) == 1
    assert rows[0]['located'] is False
    assert rows[0]['lat'] is None and rows[0]['lng'] is None
    assert rows[0]['city'] == '不存在测试城'


@pytest.mark.django_db
def test_destination_follows_last_stop():
    """`destination` 是派生的：加一站就跟着变，不许两处各说各的。"""
    plan = TravelPlan.objects.create(user_id=1, name='测试', destination='宁德')
    TravelPlanService.add_stop(plan, '泉州')
    TravelPlanService.add_stop(plan, '潮州')
    plan.refresh_from_db()
    assert plan.destination == '潮州'
