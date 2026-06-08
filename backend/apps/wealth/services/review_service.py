"""月度复盘服务 — 聚合账单流水生成复盘数据"""

from calendar import monthrange
from datetime import datetime

from django.db import connection

from apps.wealth.models import WealthBalanceList


MONTHS_MAP = {
    1: '一月', 2: '二月', 3: '三月', 4: '四月',
    5: '五月', 6: '六月', 7: '七月', 8: '八月',
    9: '九月', 10: '十月', 11: '十一月', 12: '十二月',
}


def _parse_balance_list(bi: WealthBalanceList) -> dict:
    """将 WealthBalanceList 记录转为统一字段名"""
    income_val = (bi.wageincome or 0) + (bi.otherincome or 0)
    expense_val = bi.outmoney or 0
    balance_val = bi.mbalance or 0
    deposit_val = bi.total
    deposit_balance_val = bi.balance
    savings_rate = round(balance_val / income_val * 100, 1) if income_val > 0 else 0
    return {
        'income': round(income_val, 2),
        'expense': round(expense_val, 2),
        'balance': round(balance_val, 2),
        'savings_rate': savings_rate,
        'deposit': round(deposit_val, 2) if deposit_val else None,
        'deposit_balance': round(deposit_balance_val, 2) if deposit_balance_val else None,
        'notes': bi.remarks or '',
        'from_balance_list': True,
    }


def _aggregate_from_bills(user_id: int, year: int, month: int) -> dict:
    """从 wealth_bill_list 聚合月度收支"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN transaction_type = '收入' THEN amount ELSE 0 END), 0) as total_income,
                COALESCE(SUM(CASE WHEN transaction_type = '支出' THEN amount ELSE 0 END), 0) as total_expense,
                COALESCE(MAX(CASE WHEN transaction_type = '收入' THEN amount ELSE 0 END), 0) as max_income,
                COALESCE(MAX(CASE WHEN transaction_type = '支出' THEN amount ELSE 0 END), 0) as max_expense
            FROM wealth_bill_list
            WHERE user_id = %s AND year = %s AND month = %s
        """, [user_id, year, month])
        row = cursor.fetchone()

    _, days_in_month = monthrange(year, month)
    total_income = float(row[0])
    total_expense = float(row[1])
    balance = round(total_income - total_expense, 2)
    avg_daily_expense = round(total_expense / days_in_month, 2) if days_in_month else 0

    return {
        'income': total_income,
        'expense': total_expense,
        'balance': balance,
        'savings_rate': round(balance / total_income * 100, 1) if total_income > 0 else 0,
        'avg_daily_expense': avg_daily_expense,
        'max_daily_income': float(row[2]),
        'max_daily_expense': float(row[3]),
        'days_in_month': days_in_month,
    }


def get_monthly_review(user_id: int, year: int, month: int) -> dict:
    """获取指定月份的复盘汇总 — 优先使用 balance_list，否则从账单聚合"""
    yearmon = f"{year:04d}-{month:02d}"
    yearmon_alt = f"{year}-{month:02d}"  # 兼容不同分隔符

    # 尝试从 balance_list 获取
    from_db = None
    try:
        bi = WealthBalanceList.objects.get(yearmon=yearmon)
        from_db = _parse_balance_list(bi)
    except WealthBalanceList.DoesNotExist:
        try:
            bi = WealthBalanceList.objects.get(yearmon=yearmon_alt)
            from_db = _parse_balance_list(bi)
        except WealthBalanceList.DoesNotExist:
            pass

    # 从账单聚合
    bills = _aggregate_from_bills(user_id, year, month)

    if from_db:
        result = {**bills, **from_db}
    else:
        result = {**bills, 'deposit': None, 'deposit_balance': None, 'notes': '', 'from_balance_list': False}

    # 环比计算
    mom = _calc_mom(user_id, year, month, result)
    result['mom_change'] = mom

    # 最高单日
    result['max_daily_expense_detail'] = _get_max_daily(user_id, year, month, '支出')
    result['max_daily_income_detail'] = _get_max_daily(user_id, year, month, '收入')

    result['year'] = year
    result['month'] = month
    result['month_name'] = MONTHS_MAP.get(month, '')
    return result


def _calc_mom(user_id: int, year: int, month: int, current: dict) -> dict:
    """计算环比变化（与上月对比）"""
    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    prev = _aggregate_from_bills(user_id, prev_year, prev_month)

    def pct(current_val, prev_val):
        if prev_val == 0:
            return None
        return round((current_val - prev_val) / prev_val * 100, 1)

    return {
        'income': pct(current['income'], prev['income']),
        'expense': pct(current['expense'], prev['expense']),
        'balance': pct(current['balance'], prev['balance']),
    }


def _get_max_daily(user_id: int, year: int, month: int, tx_type: str) -> dict | None:
    """获取当月某类型最大单日"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT day, MAX(amount)
            FROM wealth_bill_list
            WHERE user_id = %s AND year = %s AND month = %s
              AND transaction_type = %s
            GROUP BY day
            ORDER BY MAX(amount) DESC
            LIMIT 1
        """, [user_id, year, month, tx_type])
        row = cursor.fetchone()
    if row:
        return {'amount': float(row[1]), 'date': f"{year:04d}-{month:02d}-{row[0]:02d}"}
    return None


def get_trend_data(user_id: int, months: int = 12) -> list[dict]:
    """获取近N个月收支趋势数据"""
    today = datetime.now()
    results = []
    for i in range(months - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1

        review = get_monthly_review(user_id, y, m)
        results.append({
            'yearmon': f"{y:04d}-{m:02d}",
            'income': review['income'],
            'expense': review['expense'],
            'balance': review['balance'],
            'savings_rate': review['savings_rate'],
            'deposit': review.get('deposit'),
        })
    return results


def get_category_ranking(user_id: int, year: int, month: int, tx_type: str = '支出') -> list[dict]:
    """获取分类排行"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM wealth_bill_list
            WHERE user_id = %s AND year = %s AND month = %s
              AND transaction_type = %s
        """, [user_id, year, month, tx_type])
        total = float(cursor.fetchone()[0])

        cursor.execute("""
            SELECT category, COALESCE(SUM(amount), 0) as total_amount
            FROM wealth_bill_list
            WHERE user_id = %s AND year = %s AND month = %s
              AND transaction_type = %s
            GROUP BY category
            ORDER BY total_amount DESC
            LIMIT 5
        """, [user_id, year, month, tx_type])
        rows = cursor.fetchall()

    items = []
    for cat, amt in rows:
        amt = float(amt)
        items.append({
            'category': cat or '未分类',
            'amount': amt,
            'percentage': round(amt / total * 100, 1) if total > 0 else 0,
        })
    return items


def get_monthly_list(user_id: int, page: int = 1, page_size: int = 12) -> dict:
    """获取历史复盘列表（分页）"""
    offset = (page - 1) * page_size

    bis = WealthBalanceList.objects.all().order_by('-yearmon')
    total = bis.count()
    page_bis = bis[offset:offset + page_size]

    items = []
    for bi in page_bis:
        income_val = (bi.wageincome or 0) + (bi.otherincome or 0)
        expense_val = bi.outmoney or 0
        balance_val = bi.mbalance or 0
        deposit_val = bi.total
        savings_rate = round((income_val - expense_val) / income_val * 100, 1) if income_val > 0 else 0

        items.append({
            'yearmon': bi.yearmon,
            'income': round(income_val, 2),
            'expense': round(expense_val, 2),
            'balance': round(balance_val, 2),
            'deposit': round(deposit_val, 2) if deposit_val else None,
            'savings_rate': savings_rate,
            'notes': bi.remarks or '',
        })

    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
    }


def get_compare_data(user_id: int, year: int, month: int) -> dict:
    """同比环比分析"""
    current = get_monthly_review(user_id, year, month)

    prev_m = month - 1
    prev_y = year
    if prev_m == 0:
        prev_m = 12
        prev_y -= 1
    prev_month = get_monthly_review(user_id, prev_y, prev_m)

    yoy = get_monthly_review(user_id, year - 1, month) if year - 1 >= 2000 else None

    def diff_pct(cur, prev_val):
        if prev_val and prev_val != 0:
            return round((cur - prev_val) / prev_val * 100, 1)
        return None

    result = {
        'current': {
            'yearmon': f"{year:04d}-{month:02d}",
            'income': current['income'],
            'expense': current['expense'],
            'balance': current['balance'],
            'savings_rate': current['savings_rate'],
        },
        'mom': {
            'yearmon': f"{prev_y:04d}-{prev_m:02d}",
            'income': prev_month['income'],
            'expense': prev_month['expense'],
            'balance': prev_month['balance'],
            'income_change': diff_pct(current['income'], prev_month['income']),
            'expense_change': diff_pct(current['expense'], prev_month['expense']),
            'balance_change': diff_pct(current['balance'], prev_month['balance']),
        },
    }

    if yoy:
        result['yoy'] = {
            'yearmon': f"{year - 1:04d}-{month:02d}",
            'income': yoy['income'],
            'expense': yoy['expense'],
            'balance': yoy['balance'],
            'income_change': diff_pct(current['income'], yoy['income']),
            'expense_change': diff_pct(current['expense'], yoy['expense']),
            'balance_change': diff_pct(current['balance'], yoy['balance']),
        }

    return result


def generate_balance_info(user_id: int, year: int, month: int) -> WealthBalanceList | None:
    """从账单聚合生成复盘数据并保存到 balance_list"""
    yearmon = f"{year:04d}-{month:02d}"
    bills = _aggregate_from_bills(user_id, year, month)

    # 查找已有记录或创建
    try:
        bi = WealthBalanceList.objects.get(yearmon=yearmon)
    except WealthBalanceList.DoesNotExist:
        try:
            bi = WealthBalanceList.objects.get(yearmon=yearmon.replace('-', '-'))
        except WealthBalanceList.DoesNotExist:
            bi = None

    if bi:
        # 更新现有记录
        bi.age = float(year - 1995)  # approximate age from birth year
        bi.wageincome = bills['income']
        bi.otherincome = 0
        bi.outmoney = bills['expense']
        bi.mbalance = bills['balance']
        bi.remarks = '系统生成'
        bi.save()
        return bi

    return None
