"""「点热力图格子 → 看那一周明细」这条链路的测试 — apps.wealth.views.BillsByWeekView

对应缺陷（v3.60.16 修）：点某一格，弹窗里**有收支数字、却写「本周无账单记录」**。

真因不在数据、也不在这段 SQL，而在**路由顺序**：
`urls.py` 原来把 `path('', include(router.urls))` 排在所有静态路径**之前**，
而 DRF 的详情路由是 `bills/<pk>/`（`<pk>` 默认正则 `[^/.]+` 能匹配任何一段），
于是 `bills/by_week/` 被它接走、当成 `pk='by_week'` → **404**。
前端 store 里那句 `catch { selectedWeekBills.value = [] }` 又把 404 静默当成空数组
⇒ 「取不到」被显示成「这一周没有账单」。**两处都对得住自己，合起来是错的。**

所以本文件钉三件事：
  ① 这条 URL 必须解析到 `BillsByWeekView`（不许再被路由器抢走）；
  ② 全站 `path()` 静态路径都不许被动态路由抢走（防复发，不只守这一条）；
  ③ 弹窗里那两个数（聚合的收支 vs 明细的求和）必须**同源**——这是用户看到的矛盾本体。
"""
from datetime import date, datetime, timedelta

import pytest
from django.urls import Resolver404, URLResolver, get_resolver, resolve
from rest_framework.test import APIClient

from apps.wealth.constants import WEEKS_PER_YEAR, age_week_to_global_index
from apps.wealth.models import WealthBillList, WealthLifeWeekCalendar
from apps.wealth.services.week_aggregator import aggregate_weekly_net_income
from apps.wealth.views import BillsByWeekView

BY_WEEK_URL = '/api/wealth/bills/by_week/'

# 现场坐标：2026-10-09 用户点的那一格（31 岁第 38 周，索引 713）
WEEK_INDEX = age_week_to_global_index(31, 38)          # 713
WEEK_START = date(2026, 9, 21)                          # 周一
WEEK_END = date(2026, 9, 27)                            # 周日

# 截图里的三个数，直接拿来当期望值 —— 用例就是那张截图的断言版
SHOT_INCOME = 12754.00
SHOT_EXPENSE = 6292.72
SHOT_NET = 6461.28


def _seed_week(index: int = WEEK_INDEX, start: date = WEEK_START, user_id: int = 1,
               is_lived: bool = True) -> WealthLifeWeekCalendar:
    """造一行周历（age_year / week_number 由索引反推，与表口径一致）。"""
    return WealthLifeWeekCalendar.objects.create(
        global_week_index=index,
        age_year=18 + index // WEEKS_PER_YEAR,
        week_number=index % WEEKS_PER_YEAR + 1,
        week_start_date=start,
        week_end_date=start + timedelta(days=6),
        is_lived=is_lived,
        user_id=user_id,
    )


def _bill(when: datetime, amount: str, ttype: str = '支出', user_id: int = 1) -> WealthBillList:
    """造一条账单（打 [SMOKE] 标记，便于事后人工识别）。

    ⚠️ `created_at` / `updated_at` 在模型上是可空的，但**库里是 NOT NULL**
    （conftest 的 DDL 带 `DEFAULT CURRENT_TIMESTAMP`，而 ORM 插入会显式送 NULL）
    ⇒ 必须显式给值，否则 `IntegrityError: Column 'created_at' cannot be null`。
    `date` 用**朴素时间**：本接口走原生 SQL、拿 `date` 字面量直接比较，
    与库里现有数据的存法保持一致（用 aware 会在写入时被转成 UTC，比较就错位了）。
    """
    return WealthBillList.objects.create(
        transaction_type=ttype, date=when, amount=amount,
        category='[SMOKE]测试', subcategory='用例造数', notes='[SMOKE]',
        year=when.year, month=when.month, day=when.day,
        created_at=when, updated_at=when, user_id=user_id,
    )


def _seed_screenshot_week() -> None:
    """复刻截图那一周：两笔本周期内（含周日 23:59）、一笔下周一 00:00、一笔别人的。"""
    _seed_week()
    _bill(datetime(2026, 9, 21, 7, 57, 2), '12754.00', '收入')
    _bill(datetime(2026, 9, 27, 23, 59, 59), '6292.72', '支出')      # 本周期最后一秒
    _bill(datetime(2026, 9, 28, 0, 0, 0), '9999.99', '支出')         # 下周一 00:00，必须排除
    _bill(datetime(2026, 9, 22, 12, 0, 0), '111.00', '支出', user_id=2)  # 别人的，必须排除


# ──────────────────────────────────────────────────────────────
# 一、路由：这条路径不许再被路由器抢走
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_by_week_url_resolves_to_its_own_view() -> None:
    """🔴 缺陷本体：`bills/by_week/` 必须解析到 BillsByWeekView，而不是 `bills/<pk>/`"""
    match = resolve(BY_WEEK_URL)

    assert match.func.view_class is BillsByWeekView
    assert 'pk' not in match.kwargs


def _walk_static_paths(patterns, prefix=''):
    """递归取出所有 `path()` 声明的静态路径（带转换器的动态路径跳过）。"""
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk_static_paths(p.url_patterns, prefix + str(p.pattern))
            continue
        route = getattr(p.pattern, '_route', None)
        if route is None or '<' in route:
            continue
        yield '/' + (prefix + route).lstrip('/'), p.callback


def _view_identity(view) -> str:
    cls = getattr(view, 'view_class', None)
    return cls.__name__ if cls is not None else getattr(view, '__name__', repr(view))


@pytest.mark.django_db
def test_no_static_path_is_shadowed_by_a_dynamic_route() -> None:
    """🔴 防复发（全站，不只守 wealth）：任何 `path()` 静态路径都不许被别的视图接走。

    出现影子路由的判据：该 URL resolve 出来的视图 ≠ 它声明的视图。
    唯一豁免是 DRF 的 `APIRootView` —— 应用根视图本来就会被「用空前缀注册的
    列表路由」盖掉（如 `apps/book` 的 `register(r'')`），那是 DRF 的正常形态。
    """
    shadowed = []
    for url, declared in _walk_static_paths(get_resolver().url_patterns):
        if _view_identity(declared) == 'APIRootView':
            continue
        try:
            matched = resolve(url)
        except Resolver404:
            shadowed.append((url, _view_identity(declared), '未匹配'))
            continue
        if _view_identity(matched.func) != _view_identity(declared):
            shadowed.append((url, _view_identity(declared), _view_identity(matched.func)))

    assert shadowed == [], f'静态路径被动态路由抢走：{shadowed}'


# ──────────────────────────────────────────────────────────────
# 二、接口：真的把这一周的账单取回来了
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_week_bills_are_returned_for_a_week_with_records() -> None:
    """有账单的一周必须返回明细 —— 这是用户点开想看的那张表"""
    _seed_screenshot_week()

    body = APIClient().get(BY_WEEK_URL, {'week_index': WEEK_INDEX}).json()

    assert body['week_index'] == WEEK_INDEX
    assert body['week_start'] == WEEK_START.isoformat()
    assert body['week_end'] == WEEK_END.isoformat()
    assert len(body['bills']) == 2
    # 明细要带上弹窗渲染所需的全部键（少一个 = 那一列整列空着）
    for key in ('id', 'transaction_type', 'category', 'subcategory', 'amount', 'date', 'note'):
        assert key in body['bills'][0]


@pytest.mark.django_db
def test_week_bills_boundary_is_half_open() -> None:
    """🔴 区间是半开的 [周一 00:00, 下周一 00:00)：
    `date` 列是 **datetime**（不是 date），用 `<= 周日` 会漏掉周日当天 08:00 之后的
    全部消费。周日 23:59:59 必须算进来，下周一 00:00:00 必须算出去。
    """
    _seed_screenshot_week()

    bills = APIClient().get(BY_WEEK_URL, {'week_index': WEEK_INDEX}).json()['bills']
    dates = {b['date'] for b in bills}

    assert any(d.startswith('2026-09-27T23:59:59') for d in dates)   # 周日最后一秒
    assert not any(d.startswith('2026-09-28') for d in dates)        # 下周一


@pytest.mark.django_db
def test_week_bills_do_not_leak_other_users() -> None:
    """别人的账单不得混进来"""
    _seed_screenshot_week()

    bills = APIClient().get(BY_WEEK_URL, {'week_index': WEEK_INDEX}).json()['bills']

    assert all(b['amount'] != 111.0 for b in bills)


@pytest.mark.django_db
def test_missing_week_index_is_a_400() -> None:
    body = APIClient().get(BY_WEEK_URL).json()
    assert body == {'error': 'week_index is required'}


@pytest.mark.django_db
def test_non_numeric_week_index_is_a_400_not_a_500() -> None:
    """非数字索引过去会一路传到 ORM/原生 SQL 上炸成 500；现在要一个说得清名字的 400"""
    response = APIClient().get(BY_WEEK_URL, {'week_index': 'by_week'})

    assert response.status_code == 400
    assert response.json() == {'error': 'week_index must be an integer'}


@pytest.mark.django_db
def test_week_index_is_echoed_as_a_number() -> None:
    """🔴 回显的 `week_index` 必须是数字：前端的类型声明就是 `number`，
    回字符串会让所有「拿它做比较/查表」的地方静默不相等（'713' !== 713）。
    """
    _seed_week()

    body = APIClient().get(BY_WEEK_URL, {'week_index': WEEK_INDEX}).json()

    assert body['week_index'] == WEEK_INDEX
    assert isinstance(body['week_index'], int)


@pytest.mark.django_db
def test_unknown_week_carries_a_named_error_not_a_bare_404() -> None:
    """🔴 「周不存在」与「路由被抢」都返回 404，但 body 必须能分辨。

    被路由器抢走的 404 是 DRF 的默认体（`{"detail": ...}`）——两者混在一起时，
    前端与排查者都只能看到「404」，分不清是数据问题还是路由问题。
    """
    response = APIClient().get(BY_WEEK_URL, {'week_index': 999999})

    assert response.status_code == 404
    assert response.json() == {'error': 'week not found'}


# ──────────────────────────────────────────────────────────────
# 三、同屏两个数必须同源（用户看到的矛盾本体）
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_detail_sum_equals_the_weekly_aggregate() -> None:
    """🔴 弹窗上半部分的收支（周历聚合）与下半部分明细的求和，必须是同一个数。

    这正是用户截图里的矛盾：上面写着 +12,754.00 / -6,292.72 / +6,461.28，
    下面写着「本周无账单记录」。两条链路读同一张表、同一个半开区间，
    一旦有人改了其中一条的区间写法，这条用例会红。
    """
    _seed_screenshot_week()

    bills = APIClient().get(BY_WEEK_URL, {'week_index': WEEK_INDEX}).json()['bills']
    income = sum(float(b['amount']) for b in bills if b['transaction_type'] == '收入')
    expense = sum(float(b['amount']) for b in bills if b['transaction_type'] == '支出')

    aggregated = aggregate_weekly_net_income(1)[WEEK_INDEX]

    assert (income, expense) == (SHOT_INCOME, SHOT_EXPENSE)
    assert aggregated == {'income': SHOT_INCOME, 'expense': SHOT_EXPENSE, 'net': SHOT_NET}


# ──────────────────────────────────────────────────────────────
# 四、挪动路由器没有弄坏原有路由
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_router_list_and_detail_routes_still_work() -> None:
    """把路由器挪到最后之后，它自己的列表 / 详情路由必须照旧"""
    _seed_screenshot_week()
    one = WealthBillList.objects.filter(user_id=1).first()

    client = APIClient()
    assert client.get('/api/wealth/bills/').status_code == 200
    assert client.get(f'/api/wealth/bills/{one.id}/').status_code == 200
