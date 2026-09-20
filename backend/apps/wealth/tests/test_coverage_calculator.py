"""现金流推演算法测试 — apps.wealth.services.coverage_calculator"""
from apps.wealth.services.coverage_calculator import calculate_coverage, calculate_daily_budget


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


# ─────────────────────────────────────────────────────────────
# 反算 calculate_daily_budget —— calculate_coverage 的反函数
# ─────────────────────────────────────────────────────────────

def _simulate(cash: float, daily_budget: float, days: int, rate: float) -> float:
    """按正算同一套日循环（先扣款、再对余额计息）独立模拟，返回第 days 天末余额。"""
    balance = cash
    for _ in range(days):
        balance -= daily_budget
        if balance <= 0:
            return balance
        if rate > 0:
            balance += balance * rate
    return balance


def test_zero_rate_is_plain_division() -> None:
    """核心：无利息时，每日可提取额 = 本金 ÷ 天数（纯均摊）"""
    assert calculate_daily_budget(100000, 365, 0) == 100000 / 365
    assert calculate_daily_budget(100000, 365.28, 0) == 100000 / 365.28


def test_interest_raises_daily_budget() -> None:
    """核心：有日利息时，利息补贴使日均可花高于纯均摊（期限越长、补贴越显著）"""
    no_interest = calculate_daily_budget(100000, 3650, 0)
    with_interest = calculate_daily_budget(100000, 3650, 0.00015)
    assert with_interest > no_interest
    # 20 年期的补贴比例应大于 5 年期（复利累积更久）
    ratio_20y = calculate_daily_budget(100000, 7305.6, 0.00015) / (100000 / 7305.6)
    ratio_5y = calculate_daily_budget(100000, 1826.4, 0.00015) / (100000 / 1826.4)
    assert ratio_20y > ratio_5y


def test_closed_loop_balance_hits_zero() -> None:
    """核心：反算结果喂回同一套日循环，第 n 天末余额恰好归零（误差 < 1 元）

    这是「反函数」的实质定义 —— 也是本函数与正算口径不漂移的保障。
    """
    for days, rate in ((3652, 0), (3652, 0.00015), (10958, 0.00015), (1826, 0.001)):
        budget = calculate_daily_budget(100000, days, rate)
        balance = _simulate(100000, budget, days, rate)
        assert abs(balance) < 1.0, f'days={days} rate={rate} 余额={balance}'


def test_closed_loop_with_calculate_coverage() -> None:
    """核心：反算 → 正算闭环，支撑周数与目标天数吻合

    ⚠️ 恒比「目标天数 ÷ 7」少一周：耗尽发生在第 n 天，而该天所在的**那一周**
    算不得完整支撑（正算里 `current_cash <= 0` 即中断，该周不计入 covered_weeks，
    与 test_no_interest_support_weeks_exact 同源）。故 support = ceil(n / 7) − 1。
    """
    for days in (364, 1820, 3652):
        budget = calculate_daily_budget(100000, days, 0)
        _, support, _, _ = calculate_coverage(
            start_age=30, start_week=1, cash=100000, daily_budget=budget
        )
        expected = (days + 6) // 7 - 1  # ceil(days / 7) - 1
        assert support == expected, f'days={days} support={support} expected={expected}'


def test_perpetual_annuity_ceiling() -> None:
    """边界：期限极长时收敛到永续上限 P·r/(1+r)——本金产生的利息刚好覆盖提取

    此时本金恒定不减、永远花不完，是数学上界而非计算错误。
    """
    for rate in (0.00015, 0.001):
        ceiling = 100000 * rate / (1 + rate)
        assert abs(calculate_daily_budget(100000, 10_000_000, rate) - ceiling) < 1e-3
    # 永续点上行：用该额提取，余额既不增也不减
    rate = 0.001
    ceiling = calculate_daily_budget(100000, 10_000_000, rate)
    assert abs(_simulate(100000, ceiling, 1000, rate) - 100000) < 1.0


def test_invalid_inputs_return_zero() -> None:
    """边界：本金或天数非正 → 0（不抛异常，供前端直接判空态）"""
    assert calculate_daily_budget(0, 365, 0.00015) == 0.0
    assert calculate_daily_budget(100000, 0, 0.00015) == 0.0
    assert calculate_daily_budget(-100, 365, 0.00015) == 0.0
    assert calculate_daily_budget(100000, -1, 0.00015) == 0.0


def test_no_overflow_on_extreme_days_and_rate() -> None:
    """边界：天数与利率同取极端值时不得溢出（expm1 数值稳定性的回归保护）

    朴素写法 (1+r)**n 在 r=0.01、n=10_000_000 时会上溢为 inf → 结果变 0 或 nan。
    """
    budget = calculate_daily_budget(100000, 10_000_000, 0.01)
    assert budget > 0
    assert budget == budget  # 非 nan
    assert budget < 100000  # 合法量级
