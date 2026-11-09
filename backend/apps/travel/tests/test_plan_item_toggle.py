"""旅行计划子项「完成」入口 —— 契约与幂等守卫

🔴 背景订正（2026-10-18）：第八轮审计的 DQ-2 结论「入口缺失」**是错的**。
   前端 `toggleTravelPlanItem()` 与后端 `TravelPlanViewSet.toggle_item` 一直都在，
   `is_completed` / `completed_at` 两个字段也早就有（零迁移）。
   「106 个子项 0 个完成」的真实原因需要现场点击确认，不是路由不存在。

   这组测试守两件事：
   1. **契约**：前端用的那个 URL 必须真的能改到 `is_completed`；
   2. **幂等**：显式传 `is_completed` 时重复请求不翻转状态
      —— 旧实现「永远取反」，双击 / 重试会把刚勾上的又取消掉。
"""
import pytest
from rest_framework.test import APIClient

from apps.travel.models import TravelPlan, TravelPlanItem

PLANS_URL = '/api/travel/plans/'


def _toggle_url(plan_id: int) -> str:
    """🔴 路径**逐字**照抄前端 `travelApi.ts` 里的写法，不在这里另起一套。"""
    return f'{PLANS_URL}{plan_id}/toggle-item/'


@pytest.fixture
def plan_with_items(db):
    plan = TravelPlan.objects.create(
        user_id=1, name='测试行程', destination='龙岩', total_estimate=500,
    )
    a = TravelPlanItem.objects.create(plan=plan, item_type='scenic', name='永定土楼', estimate_cost=100)
    b = TravelPlanItem.objects.create(plan=plan, item_type='food', name='客家菜', estimate_cost=80)
    return plan, a, b


@pytest.mark.django_db
def test_toggle_item_route_exists(plan_with_items):
    """契约：前端调的这条 URL 必须真的存在且返回 200。"""
    plan, item, _ = plan_with_items
    resp = APIClient().post(_toggle_url(plan.id), {'item_id': item.id}, format='json')
    assert resp.status_code == 200, f'路由不存在或报错：{resp.status_code} {getattr(resp, "data", None)}'


@pytest.mark.django_db
def test_toggle_item_marks_completed_and_stamps_time(plan_with_items):
    """勾上 ⇒ is_completed=True 且 completed_at 被填。"""
    plan, item, _ = plan_with_items
    resp = APIClient().post(_toggle_url(plan.id), {'item_id': item.id}, format='json')

    assert resp.data['is_completed'] is True
    assert resp.data['completed_at'] is not None

    item.refresh_from_db()
    assert item.is_completed is True
    assert item.completed_at is not None


@pytest.mark.django_db
def test_toggle_item_twice_returns_to_incomplete(plan_with_items):
    """再点一次 ⇒ 回到未完成，且 completed_at 清空（不留「完成时间」的幽灵）。"""
    plan, item, _ = plan_with_items
    client = APIClient()
    client.post(_toggle_url(plan.id), {'item_id': item.id}, format='json')
    resp = client.post(_toggle_url(plan.id), {'item_id': item.id}, format='json')

    assert resp.data['is_completed'] is False
    item.refresh_from_db()
    assert item.completed_at is None


@pytest.mark.django_db
def test_toggle_item_explicit_value_is_idempotent(plan_with_items):
    """显式传 is_completed=true 两次 ⇒ 仍是 true（重试不会把状态翻回去）。"""
    plan, item, _ = plan_with_items
    client = APIClient()
    client.post(_toggle_url(plan.id), {'item_id': item.id, 'is_completed': True}, format='json')
    resp = client.post(_toggle_url(plan.id), {'item_id': item.id, 'is_completed': True}, format='json')

    assert resp.data['is_completed'] is True
    item.refresh_from_db()
    assert item.is_completed is True


@pytest.mark.django_db
def test_toggle_item_does_not_touch_siblings(plan_with_items):
    """勾一个不能动别的子项（`perform_update` 的整体替换语义会把它们全删重建）。"""
    plan, first, second = plan_with_items
    APIClient().post(_toggle_url(plan.id), {'item_id': first.id}, format='json')

    second.refresh_from_db()
    assert second.is_completed is False
    assert TravelPlanItem.objects.filter(plan=plan).count() == 2
    assert second.id == plan_with_items[2].id


@pytest.mark.django_db
def test_toggle_item_missing_item_id_is_400(plan_with_items):
    """少了 item_id ⇒ 400，且提示是「缺少 item_id」而不是含糊的 500。"""
    plan, _, _ = plan_with_items
    resp = APIClient().post(_toggle_url(plan.id), {}, format='json')
    assert resp.status_code == 400
    assert 'item_id' in str(resp.data)


@pytest.mark.django_db
def test_toggle_item_unknown_item_is_404(plan_with_items):
    """item_id 不属于这个计划 ⇒ 404，不能跨计划改别人的子项。"""
    plan, _, _ = plan_with_items
    other = TravelPlan.objects.create(user_id=1, name='另一个行程', destination='厦门')
    foreign = TravelPlanItem.objects.create(plan=other, item_type='food', name='沙茶面')

    resp = APIClient().post(_toggle_url(plan.id), {'item_id': foreign.id}, format='json')
    assert resp.status_code == 404
    foreign.refresh_from_db()
    assert foreign.is_completed is False
