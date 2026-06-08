"""人生现金流热力图系统常量定义"""

START_AGE = 18
END_AGE = 78
TOTAL_YEARS = END_AGE - START_AGE + 1  # 61
WEEKS_PER_YEAR = 52
TOTAL_WEEKS = TOTAL_YEARS * WEEKS_PER_YEAR  # 3172


def age_week_to_global_index(age: int, week: int) -> int:
    """年龄(18-78) + 周数(1-52) → 全局索引(0-3171)"""
    return (age - START_AGE) * WEEKS_PER_YEAR + (week - 1)


def global_index_to_age_week(global_index: int) -> tuple[int, int]:
    """全局索引 → (年龄, 周数)"""
    age_offset = global_index // WEEKS_PER_YEAR
    week = global_index % WEEKS_PER_YEAR + 1
    age = START_AGE + age_offset
    return age, week
