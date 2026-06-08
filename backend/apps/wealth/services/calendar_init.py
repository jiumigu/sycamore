"""周历初始化服务"""
from datetime import date, timedelta

from django.db import transaction

from apps.wealth.constants import (
    START_AGE, END_AGE, WEEKS_PER_YEAR, TOTAL_WEEKS,
    age_week_to_global_index,
)
from apps.wealth.models import WealthLifeWeekCalendar


def init_week_calendar_for_user(user_id: int, birth_date: date) -> int:
    """
    为指定用户初始化 life_week_calendar 表。
    生成 61年 × 52周 = 3172 条记录。
    返回创建的记录数。
    """
    today = date.today()
    created = 0

    records = []
    for age in range(START_AGE, END_AGE + 1):
        year = birth_date.year + age  # 出生年份 + 年龄 = 该年龄对应的日历年份
        for week in range(1, WEEKS_PER_YEAR + 1):
            idx = age_week_to_global_index(age, week)

            # 计算该年第1个周一作为第1周起点
            jan1 = date(year, 1, 1)
            first_monday = jan1 + timedelta(days=(7 - jan1.weekday()) % 7)
            week_start = first_monday + timedelta(weeks=week - 1)
            week_end = week_start + timedelta(days=6)

            is_lived = week_end <= today

            records.append(WealthLifeWeekCalendar(
                global_week_index=idx,
                age_year=age,
                week_number=week,
                week_start_date=week_start,
                week_end_date=week_end,
                is_lived=is_lived,
                user_id=user_id,
            ))

    with transaction.atomic():
        WealthLifeWeekCalendar.objects.bulk_create(records, ignore_conflicts=True)
        created = len(records)

    return created


def update_lived_status() -> int:
    """将当前日期及之前的周标记为 is_lived=True。返回更新的记录数。"""
    today = date.today()
    updated = WealthLifeWeekCalendar.objects.filter(
        week_start_date__lte=today, is_lived=False
    ).update(is_lived=True)
    return updated
