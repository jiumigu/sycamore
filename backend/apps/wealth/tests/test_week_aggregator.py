"""账单周聚合服务测试 — apps.wealth.services.week_aggregator"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.db import connection

from apps.wealth.models import WealthLifeWeekCalendar
from apps.wealth.services.week_aggregator import (
    aggregate_weekly_net_income,
    date_to_week_index,
    get_net_level,
)


def _insert_bill(*, user_id: int, transaction_type: str, dt: datetime, amount: Decimal) -> None:
    """原生 SQL 插入账单（wealth_bill_list 无 Django 模型）"""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO wealth_bill_list "
            "(transaction_type, date, category, amount, user_id, year, month, day, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())",
            [transaction_type, dt, '测试', amount, user_id, dt.year, dt.month, dt.day],
        )


def _create_lived_week(index: int, week_start: date, user_id: int = 1) -> WealthLifeWeekCalendar:
    return WealthLifeWeekCalendar.objects.create(
        global_week_index=index,
        age_year=18,
        week_number=index + 1,
        week_start_date=week_start,
        week_end_date=week_start + timedelta(days=6),
        is_lived=True,
        user_id=user_id,
    )


@pytest.mark.django_db
def test_aggregate_mixed_income_expense_net() -> None:
    """核心：周聚合收入/支出/净额正确"""
    week_start = date(2025, 1, 6)
    _create_lived_week(0, week_start)
    _insert_bill(user_id=1, transaction_type='收入', dt=datetime(2025, 1, 7, 12, 0, 0), amount=Decimal('100'))
    _insert_bill(user_id=1, transaction_type='支出', dt=datetime(2025, 1, 8, 18, 30, 0), amount=Decimal('30'))

    result = aggregate_weekly_net_income(user_id=1)

    assert result[0] == {'income': 100.0, 'expense': 30.0, 'net': 70.0}


@pytest.mark.django_db
def test_aggregate_week_without_bills_returns_zero() -> None:
    """边界：已度过但无账单的周返回 0/0/0"""
    _create_lived_week(0, date(2025, 1, 6))

    result = aggregate_weekly_net_income(user_id=1)

    assert result[0] == {'income': 0.0, 'expense': 0.0, 'net': 0.0}


@pytest.mark.django_db
def test_aggregate_includes_bill_on_week_end_day() -> None:
    """边界：账单落在 week_end 当天（含 23:59）仍属于该周（区间为 [start, end+1)）"""
    _create_lived_week(0, date(2025, 1, 6))
    _insert_bill(user_id=1, transaction_type='收入', dt=datetime(2025, 1, 12, 23, 59, 0), amount=Decimal('100'))

    result = aggregate_weekly_net_income(user_id=1)

    assert result[0]['income'] == 100.0


@pytest.mark.django_db
def test_aggregate_excludes_bill_on_next_week_start() -> None:
    """边界：账单落在下一周起始日（week_end+1）不计入当前周"""
    week_start = date(2025, 1, 6)
    _create_lived_week(0, week_start)
    _insert_bill(user_id=1, transaction_type='收入', dt=datetime(2025, 1, 13, 0, 30, 0), amount=Decimal('999'))

    result = aggregate_weekly_net_income(user_id=1)

    assert result[0] == {'income': 0.0, 'expense': 0.0, 'net': 0.0}


@pytest.mark.django_db
def test_aggregate_ignores_non_lived_week() -> None:
    """边界：未度过周即使有账单也不出现在结果中"""
    WealthLifeWeekCalendar.objects.create(
        global_week_index=0, age_year=18, week_number=1,
        week_start_date=date(2025, 1, 6), week_end_date=date(2025, 1, 12),
        is_lived=False, user_id=1,
    )
    _insert_bill(user_id=1, transaction_type='收入', dt=datetime(2025, 1, 7, 12, 0, 0), amount=Decimal('100'))

    result = aggregate_weekly_net_income(user_id=1)

    assert result == {}


@pytest.mark.django_db
def test_aggregate_only_user_own_bills() -> None:
    """边界：其他用户的账单不混入"""
    _create_lived_week(0, date(2025, 1, 6))
    _insert_bill(user_id=2, transaction_type='收入', dt=datetime(2025, 1, 7, 12, 0, 0), amount=Decimal('999'))

    result = aggregate_weekly_net_income(user_id=1)

    assert result[0] == {'income': 0.0, 'expense': 0.0, 'net': 0.0}


def test_get_net_level_positive_grading() -> None:
    """分级：正数区间（>1500 high / >500 mid / >0 low）"""
    assert get_net_level(1500.01) == 'surplus_high'
    assert get_net_level(1500) == 'surplus_mid'
    assert get_net_level(500.01) == 'surplus_mid'
    assert get_net_level(500) == 'surplus_low'
    assert get_net_level(0.01) == 'surplus_low'


def test_get_net_level_zero_and_negative() -> None:
    """分级：0 与负数区间（0=zero / ≥-500 low / ≥-1500 mid / 其余 high）"""
    assert get_net_level(0) == 'zero'
    assert get_net_level(-0.01) == 'deficit_low'
    assert get_net_level(-500) == 'deficit_low'
    assert get_net_level(-500.01) == 'deficit_mid'
    assert get_net_level(-1500) == 'deficit_mid'
    assert get_net_level(-1500.01) == 'deficit_high'


def test_date_to_week_index_known_week() -> None:
    """映射：1995-01-01 出生，2025-01-06（周一）→ 30 岁第 1 周 → 全局索引 624"""
    assert date_to_week_index(date(2025, 1, 6), date(1995, 1, 1)) == 624


def test_date_to_week_index_out_of_range() -> None:
    """边界：年龄 <18 或 >78 返回 None"""
    assert date_to_week_index(date(2010, 1, 1), date(1995, 1, 1)) is None  # 15 岁
    assert date_to_week_index(date(2080, 1, 1), date(1995, 1, 1)) is None  # 85 岁
