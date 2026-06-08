"""现金流推演算法"""
from apps.wealth.constants import (
    START_AGE, END_AGE, WEEKS_PER_YEAR, TOTAL_WEEKS,
    age_week_to_global_index,
)


def calculate_coverage(start_age: int, start_week: int, cash: float,
                       daily_budget: float) -> tuple[list[int], int, int, int]:
    """
    计算现金在给定每日预算下能支撑的周集合。

    返回: (覆盖周索引列表, 支撑周数, 耗尽年龄, 耗尽周数)
    """
    if daily_budget <= 0:
        # 预算为0 → 不花钱，无限支撑
        return [], float('inf'), None, None

    weekly_cost = daily_budget * 7
    if weekly_cost <= 0:
        return [], float('inf'), None, None

    support_weeks = int(cash // weekly_cost)
    start_index = age_week_to_global_index(start_age, start_week)
    end_index = min(start_index + support_weeks, TOTAL_WEEKS - 1)

    coverage = list(range(start_index, end_index + 1))

    # 计算耗尽时的年龄和月数
    end_age_offset = end_index // WEEKS_PER_YEAR
    end_week_num = end_index % WEEKS_PER_YEAR + 1
    end_age = START_AGE + end_age_offset

    return coverage, support_weeks, end_age, end_week_num
