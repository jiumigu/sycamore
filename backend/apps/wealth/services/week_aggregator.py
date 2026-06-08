"""账单按周聚合服务"""
from collections import defaultdict
from datetime import date

from django.db.models import Sum, Q
from django.utils.timezone import make_aware

from apps.wealth.constants import (
    START_AGE, END_AGE, WEEKS_PER_YEAR, TOTAL_WEEKS,
    age_week_to_global_index,
)
from apps.wealth.models import WealthLifeWeekCalendar


def get_user_birth_date(user_id: int) -> date:
    """获取用户出生日期。目前从周历表反推。"""
    first_week = WealthLifeWeekCalendar.objects.filter(
        user_id=user_id, global_week_index=0
    ).first()
    if first_week:
        # 18岁第1周的起始日期减18年 ≈ 出生日期
        birth_date_approx = date(
            first_week.week_start_date.year - 18,
            first_week.week_start_date.month,
            first_week.week_start_date.day,
        )
        return birth_date_approx
    from django.conf import settings
    birth_str = getattr(settings, 'WEALTH_BIRTH_DATE', '1995-01-01')
    return date.fromisoformat(birth_str)  # 从 settings 读取


def date_to_week_index(tx_date: date, birth_date: date) -> int | None:
    """
    将具体日期映射到 18-78 岁范围内的全局周索引。
    如果日期对应年龄 < 18 或 > 78，返回 None。
    """
    age = tx_date.year - birth_date.year
    # 调整：如果今年生日还没到，age - 1
    birthday_this_year = date(tx_date.year, birth_date.month, birth_date.day)
    if tx_date < birthday_this_year:
        age -= 1

    if age < START_AGE or age > END_AGE:
        return None

    # 计算是该年龄的第几周
    year_start = date(tx_date.year, 1, 1)
    # 对齐到周一
    monday = tx_date - __import__('datetime').timedelta(days=tx_date.weekday())
    days_since_year_start = (monday - year_start).days
    week_num = days_since_year_start // 7 + 1
    if week_num > WEEKS_PER_YEAR:
        week_num = WEEKS_PER_YEAR

    return age_week_to_global_index(age, week_num)


def aggregate_weekly_net_income(user_id: int) -> dict[int, dict]:
    """
    将 wealth_bill_list 中的交易记录按周聚合。
    返回: { global_week_index: { 'income': float, 'expense': float, 'net': float } }
    """
    from apps.wealth.models import WealthLifeWeekCalendar

    # 获取已度过的周
    lived_weeks = WealthLifeWeekCalendar.objects.filter(
        user_id=user_id, is_lived=True
    ).values('global_week_index', 'week_start_date', 'week_end_date')

    # 从 bill_list 按周聚合
    from django.db import connection

    result = {}

    for week in lived_weeks:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN transaction_type = '收入' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN transaction_type = '支出' THEN amount ELSE 0 END), 0) as expense
                FROM wealth_bill_list
                WHERE user_id = %s
                  AND date >= %s AND date < %s
            """, [user_id, week['week_start_date'], week['week_end_date'] + __import__('datetime').timedelta(days=1)])

            row = cursor.fetchone()
            income = float(row[0])
            expense = float(row[1])
            net = income - expense

            result[week['global_week_index']] = {
                'income': round(income, 2),
                'expense': round(expense, 2),
                'net': round(net, 2),
            }

    return result


def get_net_level(net: float) -> str:
    """净收入 → 颜色分级标识"""
    if net > 1500:
        return 'surplus_high'
    elif net > 500:
        return 'surplus_mid'
    elif net > 0:
        return 'surplus_low'
    elif net == 0:
        return 'zero'
    elif net >= -500:
        return 'deficit_low'
    elif net >= -1500:
        return 'deficit_mid'
    else:
        return 'deficit_high'
