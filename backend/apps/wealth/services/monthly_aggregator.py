"""月度账单聚合服务"""
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db import connection


def get_color_level(net: float) -> str:
    """净日收支 → 颜色等级"""
    if net > 2000:
        return 'income_high'
    elif net > 500:
        return 'income_mid'
    elif net > 0:
        return 'income_light'
    elif net == 0:
        return 'neutral'
    elif net >= -500:
        return 'expense_light'
    elif net >= -2000:
        return 'expense_mid'
    else:
        return 'expense_high'


def aggregate_monthly_days(user_id: int, year: int, month: int) -> list[dict]:
    """
    聚合指定月每日收支数据。

    返回按日期升序排列的列表，无交易日期也包含（收支为 0）。
    """
    # 使用 year/month/day 字段高效聚合
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                day,
                COALESCE(SUM(CASE WHEN transaction_type = '收入' THEN amount ELSE 0 END), 0) as day_income,
                COALESCE(SUM(CASE WHEN transaction_type = '支出' THEN amount ELSE 0 END), 0) as day_expense
            FROM wealth_bill_list
            WHERE user_id = %s AND year = %s AND month = %s
            GROUP BY day
            ORDER BY day
        """, [user_id, year, month])

        rows = cursor.fetchall()

    # 转成 dict 方便填充
    day_map = {}
    for day_num, income, expense in rows:
        day_map[day_num] = {
            'income': float(income),
            'expense': float(expense),
            'net': float(income) - float(expense),
        }

    # 填充整月每一天
    from calendar import monthrange
    _, days_in_month = monthrange(year, month)
    results = []
    for day_num in range(1, days_in_month + 1):
        if day_num in day_map:
            d = day_map[day_num]
            net = d['net']
            color_level = get_color_level(net)
            summary_parts = []
            if d['income'] > 0:
                summary_parts.append(f"+{d['income']:.0f}")
            if d['expense'] > 0:
                summary_parts.append(f"-{d['expense']:.0f}")
            summary_text = '/'.join(summary_parts) if summary_parts else ''

            results.append({
                'date': f"{year:04d}-{month:02d}-{day_num:02d}",
                'day': day_num,
                'income': d['income'],
                'expense': d['expense'],
                'net': net,
                'summary_text': summary_text,
                'color_level': color_level,
            })
        else:
            results.append({
                'date': f"{year:04d}-{month:02d}-{day_num:02d}",
                'day': day_num,
                'income': 0,
                'expense': 0,
                'net': 0,
                'summary_text': '',
                'color_level': 'neutral',
            })

    return results


def get_daily_detail(user_id: int, target_date: date) -> dict:
    """
    获取单日收支明细。

    返回 { income_total, expense_total, net, income_list, expense_list }。
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, transaction_type, category, subcategory, amount,
                   project, account, merchant, notes, date
            FROM wealth_bill_list
            WHERE user_id = %s AND DATE(date) = %s
            ORDER BY date DESC
        """, [user_id, target_date])

        columns = [
            'id', 'transaction_type', 'category', 'subcategory', 'amount',
            'project', 'account', 'merchant', 'notes', 'date',
        ]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    income_list = [r for r in rows if r['transaction_type'] == '收入']
    expense_list = [r for r in rows if r['transaction_type'] == '支出']
    total_income = sum(r['amount'] for r in income_list)
    total_expense = sum(r['amount'] for r in expense_list)

    return {
        'income_total': float(total_income),
        'expense_total': float(total_expense),
        'net': float(total_income - total_expense),
        'income_list': income_list,
        'expense_list': expense_list,
    }


def calculate_monthly_summary(user_id: int, year: int, month: int) -> dict:
    """
    计算月度汇总统计。
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                transaction_type,
                COALESCE(SUM(amount), 0) as total,
                COALESCE(MAX(amount), 0) as max_amount
            FROM wealth_bill_list
            WHERE user_id = %s AND year = %s AND month = %s
            GROUP BY transaction_type
        """, [user_id, year, month])

        rows = cursor.fetchall()

    total_income = 0.0
    total_expense = 0.0
    max_income = 0.0
    max_expense = 0.0
    for type_, total, max_amt in rows:
        if type_ == '收入':
            total_income = float(total)
            max_income = float(max_amt)
        elif type_ == '支出':
            total_expense = float(total)
            max_expense = float(max_amt)

    from calendar import monthrange
    _, days_in_month = monthrange(year, month)

    balance = round(total_income - total_expense, 2)
    avg_daily_expense = round(total_expense / days_in_month, 2) if days_in_month > 0 else 0.0

    # 支出分类 TOP3
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT category, COALESCE(SUM(amount), 0) as total
            FROM wealth_bill_list
            WHERE user_id = %s AND year = %s AND month = %s
              AND transaction_type = '支出'
            GROUP BY category
            ORDER BY total DESC
            LIMIT 3
        """, [user_id, year, month])
        expense_top3 = [
            {'category': row[0] or '未分类', 'amount': float(row[1])}
            for row in cursor.fetchall()
        ]

    # 收入来源 TOP3
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT category, COALESCE(SUM(amount), 0) as total
            FROM wealth_bill_list
            WHERE user_id = %s AND year = %s AND month = %s
              AND transaction_type = '收入'
            GROUP BY category
            ORDER BY total DESC
            LIMIT 3
        """, [user_id, year, month])
        income_top3 = [
            {'category': row[0] or '未分类', 'amount': float(row[1])}
            for row in cursor.fetchall()
        ]

    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'avg_daily_expense': avg_daily_expense,
        'max_daily_income': max_income,
        'max_daily_expense': max_expense,
        'expense_top3': expense_top3,
        'income_top3': income_top3,
    }
