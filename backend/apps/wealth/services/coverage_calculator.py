"""现金流推演算法"""
import math

from apps.wealth.constants import (
    START_AGE, END_AGE, WEEKS_PER_YEAR,
    age_week_to_global_index,
)


def calculate_coverage(start_age: int, start_week: int, cash: float,
                       daily_budget: float,
                       daily_interest_rate: float = 0,
                       max_age: int = END_AGE) -> tuple[list[int], int | None, int | None, int | None]:
    """
    计算现金在给定每日预算下能支撑的周集合。

    daily_interest_rate: 日利息率（小数，如 0.00015 = 万分之1.5）
    利息每天复利计算，每日扣除预算后计息，每周循环 7 天。

    max_age: 推演上限年龄，默认走到数据层上限 END_AGE（78 岁）。
        财富页按**计量窗口**传 WINDOW_END_AGE（60 岁）—— 窗口之外的现金流
        不再关心，跑满窗口未耗尽即视为「覆盖至窗口末端」。
        赎回期同步（redemption.sync_to_scenario）同样传窗口上限，保证写入
        WealthCurrentScenario 的口径与财富页展示一致。

    返回: (覆盖周索引列表, 支撑周数/None表示首周即耗尽, 耗尽年龄, 耗尽周数)
    """
    weekly_cost = daily_budget * 7
    if weekly_cost <= 0 and daily_interest_rate <= 0:
        return [], None, None, None

    start_index = age_week_to_global_index(start_age, start_week)
    max_index = age_week_to_global_index(min(max_age, END_AGE), WEEKS_PER_YEAR)
    if max_index < start_index:
        # 起点已在推演上限之外：无周可覆盖
        return [], None, None, None

    current_cash = cash
    covered_weeks: list[int] = []
    end_age: int | None = None
    end_week: int | None = None

    for week_offset in range(max_index - start_index + 1):
        current_index = start_index + week_offset

        # 本周每日循环：先扣当日预算，再计当日利息
        for _day in range(7):
            current_cash -= daily_budget
            if current_cash <= 0:
                break
            if daily_interest_rate > 0:
                current_cash += current_cash * daily_interest_rate

        if current_cash <= 0:
            end_age_offset = current_index // WEEKS_PER_YEAR
            end_week_num = current_index % WEEKS_PER_YEAR + 1
            end_age = START_AGE + end_age_offset
            end_week = end_week_num
            break

        covered_weeks.append(current_index)

    support_weeks = len(covered_weeks) if covered_weeks else None

    return covered_weeks, support_weeks, end_age, end_week


def calculate_daily_budget(cash: float, days: float,
                           daily_interest_rate: float = 0) -> float:
    """`calculate_coverage` 的反函数：给本金与目标天数，求每日可提取额。

    与正算**共享同一套现金流假设**（每日先扣款、再对余额按日利率复利），
    因此结果可直接喂回 `calculate_coverage` 做闭环校验，两边数字不会打架。

    推导（本金 P、日利率 r、天数 n、每日提取 b）：

        每日递推  cash_k = (cash_{k-1} − b)(1 + r)
        展开      cash_n = P(1+r)^n − b(1+r)·[(1+r)^n − 1] / r
        令 cash_n = 0 解出
                  b = P·r·(1+r)^(n−1) / [(1+r)^n − 1]

    实现用数值稳定形式（x = n·ln(1+r)，靠 `expm1` 避免大 n 时溢出或精度丢失）：

                  b = P·r / [(1+r)·(1 − e^(−x))]

    其中 n 很大时 e^(−x) → 0，分母收敛到 (1+r)，b → P·r/(1+r)：即**永续年金**上限
    （本金产生的日利息刚好覆盖提取，本金不再减少）。r = 0 时退化为纯均摊 b = P/n。

    ⚠️ 与正算的一个已知细微差异：正算在「扣款后余额 ≤ 0」的当天立即中断且**不计息**，
    而解析解假设每天都走完「扣款 → 计息」。故 b 略偏乐观（差额 < 单日利息），
    使实际撑到第 n 天而非第 n+1 天——对「N 年怎么花」这类规划量级无感。

    返回: 每日可提取额（元/天）；本金或天数非正时返回 0.0
    """
    cash = float(cash or 0)
    days = float(days or 0)
    rate = float(daily_interest_rate or 0)

    if cash <= 0 or days <= 0:
        return 0.0
    if rate <= 0:
        return cash / days

    x = days * math.log1p(rate)
    denominator = (1 + rate) * (-math.expm1(-x))
    if denominator <= 0:
        # 理论上不可达（x>0 时恒为正），仅作除零兜底
        return cash / days

    return cash * rate / denominator
