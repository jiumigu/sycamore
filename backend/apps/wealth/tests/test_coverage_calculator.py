"""现金流推演算法测试 — apps.wealth.services.coverage_calculator"""
from apps.wealth.services.coverage_calculator import calculate_coverage


def test_no_interest_support_weeks_exact() -> None:
    """核心：无利息时支撑周数 = 现金 ÷ 周预算（耗尽周不计入）"""
    covered, support, end_age, end_week = calculate_coverage(
        start_age=30, start_week=1, cash=1000, daily_budget=100
    )
    # 1000 元 ÷ 700/周：第 1 周全数支撑，第 2 周第 3 天耗尽
    assert support == 1
    assert covered == [624]  # (30-18)*52 + 0
    assert end_age == 30
    assert end_week == 2


def test_daily_interest_extends_coverage() -> None:
    """核心：日利息复利延长支撑周数（耗尽周不计入，故以周数变多为证）"""
    _, support_plain, _, _ = calculate_coverage(
        start_age=30, start_week=1, cash=1000, daily_budget=100, daily_interest_rate=0
    )
    _, support_interest, _, _ = calculate_coverage(
        start_age=30, start_week=1, cash=1000, daily_budget=100, daily_interest_rate=0.1
    )
    assert support_plain == 1
    assert support_interest > support_plain


def test_zero_budget_zero_rate_never_exhausts() -> None:
    """边界：预算与利率均为 0 → 永不耗尽"""
    covered, support, end_age, end_week = calculate_coverage(
        start_age=30, start_week=1, cash=100, daily_budget=0
    )
    assert support is None
    assert end_age is None
    assert end_week is None
    assert covered == []


def test_negative_budget_never_exhausts() -> None:
    """边界：负预算（无支出）→ 永不耗尽"""
    _, support, _, _ = calculate_coverage(
        start_age=30, start_week=1, cash=100, daily_budget=-10
    )
    assert support is None


def test_zero_cash_no_coverage() -> None:
    """边界：现金为 0 时无任何支撑周"""
    covered, support, _, _ = calculate_coverage(
        start_age=30, start_week=1, cash=0, daily_budget=100
    )
    assert covered == []
    assert support is None


def test_last_week_start_index_valid() -> None:
    """边界：最后一年最后一周起点仍在范围内（78 岁第 52 周）"""
    covered, support, _, _ = calculate_coverage(
        start_age=78, start_week=52, cash=10000, daily_budget=1
    )
    assert covered[0] == 3171  # 全局最后一周
    assert support == 1
