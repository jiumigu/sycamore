"""现金盘点服务 — 资产全景、趋势、健康指标、对账"""

from datetime import datetime

from django.db.models import Value
from django.db.models.functions import Replace

from apps.wealth.models import WealthCashFlow


def get_cashflow_overview(user_id: int = 1) -> dict | None:
    """获取最新资产全景"""
    latest = WealthCashFlow.objects.filter(btime__isnull=False).order_by('-btime').first()
    if not latest:
        latest = WealthCashFlow.objects.order_by('-baid').first()
    if not latest:
        return None
    return _build_overview(latest)


def get_cashflow_by_yearmon(yearmon: str) -> dict | None:
    """按年月获取资产快照"""
    try:
        cf = WealthCashFlow.objects.get(yearmon=yearmon)
        return _build_overview(cf)
    except WealthCashFlow.DoesNotExist:
        return None


def _build_overview(cf: WealthCashFlow) -> dict:
    """构建资产全景响应"""
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

    flow_total = sum([
        cf.zplay or 0, cf.wechat or 0, cf.cash or 0,
        cf.jianbank or 0, cf.gongbank or 0,
        cf.zhongbank or 0, cf.nongbank or 0,
    ])
    total_assets = flow_total + (cf.accumulationfund or 0)
    borrow = cf.borrow or 0
    lend = cf.lend or 0
    realnum = total_assets - borrow + lend

    # 紧急备用金 = 现金类资产（支付宝+微信+现金）
    emergency_fund = (cf.zplay or 0) + (cf.wechat or 0) + (cf.cash or 0)

    # 负债率
    debt_ratio = round(borrow / total_assets * 100, 1) if total_assets > 0 else 0

    # 活期占比
    liquidity = flow_total  # 所有非公积金都算活期
    liquidity_ratio = round(liquidity / total_assets * 100, 1) if total_assets > 0 else 0

    # 公积金占比
    pf_ratio = round((cf.accumulationfund or 0) / total_assets * 100, 1) if total_assets > 0 else 0

    return {
        'snapshot_date': str(cf.btime) if cf.btime else None,
        'yearmon': cf.yearmon,
        'accounts': accounts,
        'summary': {
            'flow_total': round(flow_total, 2),
            'total': round(total_assets, 2),
            'borrow': round(borrow, 2),
            'lend': round(lend, 2),
            'realnum': round(realnum, 2),
        },
        'health_metrics': {
            'emergency_fund': round(emergency_fund, 2),
            'liquidity_ratio': liquidity_ratio,
            'debt_ratio': debt_ratio,
            'provident_fund_ratio': pf_ratio,
        },
    }


def get_asset_trend(user_id: int = 1, months: int = 12) -> list[dict]:
    """获取资产趋势数据"""
    records = WealthCashFlow.objects.filter(
        yearmon__isnull=False
    ).order_by('-yearmon')[:months]

    trend = []
    for r in reversed(list(records)):
        flow_total = sum([
            r.zplay or 0, r.wechat or 0, r.cash or 0,
            r.jianbank or 0, r.gongbank or 0,
            r.zhongbank or 0, r.nongbank or 0,
        ])
        total_assets = flow_total + (r.accumulationfund or 0)
        trend.append({
            'yearmon': r.yearmon,
            'flow_total': round(flow_total, 2),
            'total': round(total_assets, 2),
            'accumulationfund': round(r.accumulationfund or 0, 2),
            'zplay': round(r.zplay or 0, 2),
            'wechat': round(r.wechat or 0, 2),
            'jianbank': round(r.jianbank or 0, 2),
            'gongbank': round(r.gongbank or 0, 2),
            'zhongbank': round(r.zhongbank or 0, 2),
            'nongbank': round(r.nongbank or 0, 2),
            'borrow': round(r.borrow or 0, 2),
            'lend': round(r.lend or 0, 2),
        })
    return trend


def get_snapshot_list(page: int = 1, page_size: int = 12) -> dict:
    """获取盘点历史列表（分页）"""
    offset = (page - 1) * page_size
    qs = WealthCashFlow.objects.filter(yearmon__isnull=False).order_by('-yearmon')
    total = qs.count()
    items = list(qs[offset:offset + page_size])

    result_items = []
    for item in items:
        flow_total = sum([
            item.zplay or 0, item.wechat or 0, item.cash or 0,
            item.jianbank or 0, item.gongbank or 0,
            item.zhongbank or 0, item.nongbank or 0,
        ])
        total_assets = flow_total + (item.accumulationfund or 0)
        result_items.append({
            'baid': item.baid,
            'yearmon': item.yearmon,
            'btime': str(item.btime) if item.btime else None,
            'flow_total': round(flow_total, 2),
            'total': round(total_assets, 2),
            'zplay': round(item.zplay or 0, 2),
            'wechat': round(item.wechat or 0, 2),
            'cash': round(item.cash or 0, 2),
            'jianbank': round(item.jianbank or 0, 2),
            'gongbank': round(item.gongbank or 0, 2),
            'zhongbank': round(item.zhongbank or 0, 2),
            'nongbank': round(item.nongbank or 0, 2),
            'accumulationfund': round(item.accumulationfund or 0, 2),
            'realnum': round(item.realnum or 0, 2),
            'borrow': round(item.borrow or 0, 2),
            'lend': round(item.lend or 0, 2),
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
