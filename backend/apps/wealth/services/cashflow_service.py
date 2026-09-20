"""现金盘点服务 — 资产全景、趋势、健康指标、对账

口径（v3.58.19 财务规划口径纠偏，常量见 apps/wealth/constants.py）：
    金融资产 = 活期账户 + 公积金            → summary.total（数值不变，仅前端标签归位）
    总资产   = 金融资产 + 应收借出          → summary.total_assets
    净资产   = 总资产 − 负债                → summary.net_worth
比率类指标（负债率/活期占比/公积金占比）统一以**总资产**为分母，三者可比；
应急金以「月数」判定，不再用绝对金额。
"""

from datetime import datetime

from django.db import connection
from django.db.models import Value
from django.db.models.functions import Replace

from apps.wealth.constants import (
    EMERGENCY_MONTHS_TARGET,
    EXPENSE_LOOKBACK_MONTHS,
    LIQUID_ACCOUNT_FIELDS,
)
from apps.wealth.models import WealthCashFlow


def sum_liquid_accounts(cf) -> float:
    """活期类账户合计 — 应急金分子。

    科目以 constants.LIQUID_ACCOUNT_FIELDS 为单一真源：
    含银行卡活期（T+0 可取而原实现漏计），不含公积金与定期存款。
    """
    return sum(float(getattr(cf, f, None) or 0) for f in LIQUID_ACCOUNT_FIELDS)


def get_recent_monthly_expense(user_id: int = 1,
                               months: int = EXPENSE_LOOKBACK_MONTHS) -> float:
    """近 N 个自然月的平均月支出 — 应急金月数的分母。

    取数优先级：
      ① wealth_bill_list 明细聚合：对近 N 个自然月中**有支出记录**的月份求均值，
         除数取「有记录的月份数」而非固定 N —— 若除以 N，无记录月份会被当成
         零支出，把月均拉低、月数虚高；
      ② 明细查无数据时回落到 wealth_balance_list.outmoney 的最近 N 条；
      ③ 两者皆无数据返回 0.0，调用方据此把月数类指标置为 None。

    用账单自带的 year/month 列做月份过滤，不碰 date 字段 ——
    wealth_bill_list.date 是 datetime 且受 USE_TZ 影响，按日期推导须用半开区间。
    """
    anchor = datetime.now()
    year, month = anchor.year, anchor.month
    ym_keys: list[int] = []
    for _ in range(months):
        ym_keys.append(year * 100 + month)
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    placeholders = ','.join(['%s'] * len(ym_keys))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0)
            FROM wealth_bill_list
            WHERE user_id = %s AND transaction_type = '支出'
              AND (`year` * 100 + `month`) IN ({placeholders})
            GROUP BY `year`, `month`
            """,
            [user_id, *ym_keys],
        )
        rows = cursor.fetchall()

    active = [float(r[0]) for r in rows if r and r[0]]
    if active:
        return round(sum(active) / len(active), 2)

    from apps.wealth.models import WealthBalanceList

    fallback = [
        float(b.outmoney) for b in
        WealthBalanceList.objects.exclude(outmoney__isnull=True).order_by('-yearmon')[:months]
        if b.outmoney
    ]
    if fallback:
        return round(sum(fallback) / len(fallback), 2)
    return 0.0


def get_cashflow_overview(user_id: int = 1) -> dict | None:
    """获取最新资产全景（含按当前支出水平折算的应急金月数）"""
    latest = WealthCashFlow.objects.filter(btime__isnull=False).order_by('-btime').first()
    if not latest:
        latest = WealthCashFlow.objects.order_by('-baid').first()
    if not latest:
        return None
    return _build_overview(latest, get_recent_monthly_expense(user_id))


def get_cashflow_by_yearmon(yearmon: str) -> dict | None:
    """按年月获取资产快照（历史回看，不折算月数）"""
    try:
        cf = WealthCashFlow.objects.get(yearmon=yearmon)
        return _build_overview(cf)
    except WealthCashFlow.DoesNotExist:
        return None


def _build_overview(cf: WealthCashFlow, monthly_expense_avg: float = 0.0) -> dict:
    """构建资产全景响应

    monthly_expense_avg: 近 N 月平均月支出；传 0 表示无数据，月数类指标置 None。
    """
    accounts = {
        'zplay': cf.zplay or 0,
        'wechat': cf.wechat or 0,
        'cash': cf.cash or 0,
        'jianbank': cf.jianbank or 0,
        'gongbank': cf.gongbank or 0,
        'zhongbank': cf.zhongbank or 0,
        'nongbank': cf.nongbank or 0,
        'accumulationfund': cf.accumulationfund or 0,
    }

    flow_total = sum_liquid_accounts(cf)
    accumulationfund = float(cf.accumulationfund or 0)
    borrow = float(cf.borrow or 0)
    lend = float(cf.lend or 0)

    financial_assets = flow_total + accumulationfund   # wealth_cash_flow.total 的既有口径
    total_assets = financial_assets + lend             # 总资产：补回应收借出
    net_worth = total_assets - borrow                  # 净资产（数值等于原 realnum）

    # 应急金 = 活期类账户合计（含银行卡活期）；月数需月均支出方可折算
    emergency_fund = flow_total
    if monthly_expense_avg > 0:
        emergency_months = round(emergency_fund / monthly_expense_avg, 1)
        emergency_target_amount = round(monthly_expense_avg * EMERGENCY_MONTHS_TARGET, 2)
        emergency_gap = round(max(emergency_target_amount - emergency_fund, 0), 2)
    else:
        emergency_months = None
        emergency_target_amount = None
        emergency_gap = None

    # 三个占比指标统一以「总资产」为分母，保证互相可比
    debt_ratio = round(borrow / total_assets * 100, 1) if total_assets > 0 else 0
    debt_ratio_legacy = round(borrow / financial_assets * 100, 1) if financial_assets > 0 else 0
    liquidity_ratio = round(flow_total / total_assets * 100, 1) if total_assets > 0 else 0
    pf_ratio = round(accumulationfund / total_assets * 100, 1) if total_assets > 0 else 0

    return {
        'snapshot_date': str(cf.btime) if cf.btime else None,
        'yearmon': cf.yearmon,
        'accounts': accounts,
        'summary': {
            'flow_total': round(flow_total, 2),
            'total': round(financial_assets, 2),
            'financial_assets': round(financial_assets, 2),
            'total_assets': round(total_assets, 2),
            'net_worth': round(net_worth, 2),
            'borrow': round(borrow, 2),
            'lend': round(lend, 2),
            'realnum': round(net_worth, 2),
        },
        'health_metrics': {
            'emergency_fund': round(emergency_fund, 2),
            'emergency_fund_months': emergency_months,
            'emergency_months_target': EMERGENCY_MONTHS_TARGET,
            'emergency_target_amount': emergency_target_amount,
            'emergency_gap': emergency_gap,
            'monthly_expense_avg': round(monthly_expense_avg, 2),
            'liquidity_ratio': liquidity_ratio,
            'debt_ratio': debt_ratio,
            'debt_ratio_legacy': debt_ratio_legacy,
            'provident_fund_ratio': pf_ratio,
        },
    }


def get_asset_trend(user_id: int = 1, months: int = 12) -> list[dict]:
    """获取资产趋势数据（每月含流动性、金融资产、总资产、净资产）"""
    records = WealthCashFlow.objects.filter(
        yearmon__isnull=False
    ).order_by('-yearmon')[:months]

    trend = []
    for r in reversed(list(records)):
        flow_total = sum_liquid_accounts(r)
        accumulationfund = float(r.accumulationfund or 0)
        borrow = float(r.borrow or 0)
        lend = float(r.lend or 0)
        financial_assets = flow_total + accumulationfund
        total_assets = financial_assets + lend
        trend.append({
            'yearmon': r.yearmon,
            'flow_total': round(flow_total, 2),
            'total': round(financial_assets, 2),
            'financial_assets': round(financial_assets, 2),
            'total_assets': round(total_assets, 2),
            'net_worth': round(total_assets - borrow, 2),
            'accumulationfund': round(accumulationfund, 2),
            'zplay': round(r.zplay or 0, 2),
            'wechat': round(r.wechat or 0, 2),
            'jianbank': round(r.jianbank or 0, 2),
            'gongbank': round(r.gongbank or 0, 2),
            'zhongbank': round(r.zhongbank or 0, 2),
            'nongbank': round(r.nongbank or 0, 2),
            'borrow': round(borrow, 2),
            'lend': round(lend, 2),
        })
    return trend


def get_snapshot_list(page: int = 1, page_size: int = 12) -> dict:
    """获取盘点历史列表（分页）"""
    offset = (page - 1) * page_size
    qs = WealthCashFlow.objects.filter(yearmon__isnull=False).order_by('-btime')
    total = qs.count()
    items = list(qs[offset:offset + page_size])

    result_items = []
    for item in items:
        flow_total = sum_liquid_accounts(item)
        accumulationfund = float(item.accumulationfund or 0)
        borrow = float(item.borrow or 0)
        lend = float(item.lend or 0)
        financial_assets = flow_total + accumulationfund
        total_assets = financial_assets + lend
        net_worth = total_assets - borrow
        result_items.append({
            'baid': item.baid,
            'yearmon': item.yearmon,
            'btime': str(item.btime) if item.btime else None,
            'flow_total': round(flow_total, 2),
            'total': round(financial_assets, 2),
            'financial_assets': round(financial_assets, 2),
            'total_assets': round(total_assets, 2),
            'net_worth': round(net_worth, 2),
            'zplay': round(item.zplay or 0, 2),
            'wechat': round(item.wechat or 0, 2),
            'cash': round(item.cash or 0, 2),
            'jianbank': round(item.jianbank or 0, 2),
            'gongbank': round(item.gongbank or 0, 2),
            'zhongbank': round(item.zhongbank or 0, 2),
            'nongbank': round(item.nongbank or 0, 2),
            'accumulationfund': round(accumulationfund, 2),
            'realnum': round(net_worth, 2),
            'borrow': round(borrow, 2),
            'lend': round(lend, 2),
            'remarks': item.remarks or '',
        })

    return {
        'items': result_items,
        'total': total,
        'page': page,
        'page_size': page_size,
    }


def reconcile(user_id: int = 1, yearmon: str | None = None) -> dict:
    """账面 vs 实际对账 — 比较 balance_list 结余与 cash_flow 总资产差额"""
    from apps.wealth.models import WealthBalanceList

    if yearmon:
        bis = list(WealthBalanceList.objects.filter(yearmon=yearmon))
    else:
        # 取最新一期
        bis = list(WealthBalanceList.objects.all().order_by('-yearmon')[:1])

    # 用 dict 做按年月的快速查找，避免在已切片 QuerySet 上再 filter
    yearmons = [bi.yearmon for bi in bis]
    cfs_list = list(WealthCashFlow.objects.filter(yearmon__in=yearmons))
    cfs_by_yearmon = {cf.yearmon: cf for cf in cfs_list}

    result = {'items': [], 'summary': {'matched': 0, 'mismatched': 0}}

    for bi in bis:
        cf = cfs_by_yearmon.get(bi.yearmon)
        if not cf:
            continue

        flow_total = sum([
            cf.zplay or 0, cf.wechat or 0, cf.cash or 0,
            cf.jianbank or 0, cf.gongbank or 0,
            cf.zhongbank or 0, cf.nongbank or 0,
        ])
        total_assets = flow_total + (cf.accumulationfund or 0)
        book_balance = float(bi.balance) if bi.balance else 0
        diff = round(book_balance - total_assets, 2)

        item = {
            'yearmon': bi.yearmon,
            'book_balance': book_balance,
            'actual_total': round(total_assets, 2),
            'difference': diff,
            'status': 'matched' if abs(diff) < 0.01 else 'mismatched',
        }
        result['items'].append(item)
        if item['status'] == 'matched':
            result['summary']['matched'] += 1
        else:
            result['summary']['mismatched'] += 1

    return result


def create_or_update_snapshot(data: dict) -> WealthCashFlow:
    """创建或更新现金盘点记录"""
    yearmon = data.get('yearmon')
    if not yearmon:
        raise ValueError('yearmon is required')

    defaults = {
        'zplay': data.get('zplay', 0),
        'wechat': data.get('wechat', 0),
        'cash': data.get('cash', 0),
        'jianbank': data.get('jianbank', 0),
        'gongbank': data.get('gongbank', 0),
        'zhongbank': data.get('zhongbank', 0),
        'nongbank': data.get('nongbank', 0),
        'accumulationfund': data.get('accumulationfund', 0),
        'lend': data.get('lend', 0),
        'borrow': data.get('borrow', 0),
        'remarks': data.get('remarks', ''),
        'btime': data.get('btime') or datetime.now().date(),
    }

    flow_total = sum([
        float(defaults['zplay']), float(defaults['wechat']),
        float(defaults['cash']), float(defaults['jianbank']),
        float(defaults['gongbank']), float(defaults['zhongbank']),
        float(defaults['nongbank']),
    ])
    total_assets = flow_total + float(defaults['accumulationfund'])
    defaults['flow_total'] = round(flow_total, 2)
    defaults['total'] = round(total_assets, 2)
    defaults['realnum'] = round(total_assets - float(defaults['borrow']) + float(defaults['lend']), 2)

    obj, _ = WealthCashFlow.objects.update_or_create(
        yearmon=yearmon,
        defaults=defaults,
    )
    return obj


def copy_last_month(yearmon: str) -> WealthCashFlow | None:
    """复制上月的盘点数据到指定年月"""
    yearmon_norm = yearmon.replace('-', '')
    records = WealthCashFlow.objects.filter(
        yearmon__isnull=False
    ).annotate(
        yearmon_clean=Replace('yearmon', Value('-'), Value(''))
    ).filter(
        yearmon_clean__lt=yearmon_norm
    ).order_by('-yearmon_clean')
    last = records.first()
    if not last:
        return None

    data = {
        'yearmon': yearmon,
        'zplay': last.zplay or 0,
        'wechat': last.wechat or 0,
        'cash': last.cash or 0,
        'jianbank': last.jianbank or 0,
        'gongbank': last.gongbank or 0,
        'zhongbank': last.zhongbank or 0,
        'nongbank': last.nongbank or 0,
        'accumulationfund': last.accumulationfund or 0,
        'lend': last.lend or 0,
        'borrow': last.borrow or 0,
        'remarks': f'从{last.yearmon}复制',
    }
    return create_or_update_snapshot(data)
