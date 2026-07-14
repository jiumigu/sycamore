"""现金流推演算法"""
from apps.wealth.constants import (
    START_AGE, WEEKS_PER_YEAR, TOTAL_WEEKS,
    age_week_to_global_index,
)


def calculate_coverage(start_age: int, start_week: int, cash: float,
                       daily_budget: float,
                       daily_interest_rate: float = 0) -> tuple[list[int], int | None, int | None, int | None]:
    """
    计算现金在给定每日预算下能支撑的周集合。

    daily_interest_rate: 日利息率（小数，如 0.00015 = 万分之1.5）
    利息每天复利计算，每日扣除预算后计息，每周循环 7 天。

    返回: (覆盖周索引列表, 支撑周数/None表示永不耗尽, 耗尽年龄, 耗尽周数)
    """
    weekly_cost = daily_budget * 7
    if weekly_cost <= 0 and daily_interest_rate <= 0:
        return [], None, None, None

    start_index = age_week_to_global_index(start_age, start_week)
    current_cash = cash
    covered_weeks: list[int] = []
    end_age: int | None = None
    end_week: int | None = None

    for week_offset in range(TOTAL_WEEKS - start_index):
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
