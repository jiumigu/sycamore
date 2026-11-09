"""净资产变动归因 —— 把「资产表」和「收支表」勾稽起来

回答的问题
    这期净值涨了 4,286 元，是**存下来的**，还是**还了债 / 记漏了 / 余额抄错了**？

为什么需要它
    资产盘点回答「我现在有多少」，账本回答「这段时间进出多少」——
    两张表各自都对，却从来没人问过它们**对不对得上**。
    个人财务里最贵的一类错误（漏记一笔大额支出、把还款记成消费、
    账户余额抄错一位）在两张表分开放的时候**完全不可见**：
    资产表只会安静地少一截，看起来像「这个月花得多了点」。

口径（唯一真源，恒等式由测试锁住）
    Δ净资产 = Δ总资产 − Δ负债                                    （定义）
    Δ总资产 = 账本净流量 + 未解释差额                                （分解）
    账本净流量 = 收入 − 支出 + 余额变更
    未解释差额 = Δ总资产 − 账本净流量                                （★ 这才是要看的数）

    ⇒  Δ净资产 = 账本净流量 + 未解释差额 − Δ负债

🔴 为什么「未解释差额」只算**资产端**，不把 Δ负债 减进去：
    还款时「现金 −8500、负债 −8500」，净资产一分没变。
      · 若这笔记进了账本（支出 8500）⇒ 资产端差额 = 0，Δ负债 已单列 ⇒ 不报警 ✅
      · 若这笔记漏了         ⇒ 资产端差额 = −8500 ⇒ 报警「8500 现金流出没有账」✅
    若按「差额 = Δ净资产 − 账本净流量 + Δ负债」的写法，
    上面第二种情况会被算成 +0 而**静默放过**，第一种情况反而报警 ——
    正好反了。所以 Δ负债 只作为**独立一行**展示，绝不混进差额。

区间口径 = `(上期盘点日, 本期盘点日]`
    ⚠️ 只能用**日期**划界，不能用 `__date`（`USE_TZ` 下撞 `CONVERT_TZ`，§55/§94.3）。
    ⚠️ 账单精确到秒、盘点只到日 ⇒ 盘点当天谁先谁后无法判定，
       所以**起点日整天排除、终点日整天纳入**，边界噪声落在差额里（通常 < 100 元）。
"""

from datetime import datetime, time, timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from apps.wealth.constants import BRIDGE_MATERIAL_AMOUNT
from apps.wealth.models import WealthBillList

INCOME = '收入'
EXPENSE = '支出'
ADJUST = '余额变更'


def _f(value) -> float:
    return float(value or 0)


def _r2(value) -> float:
    return round(_f(value), 2)


def _asset_position():
    """资产位置解析的桥（同 `cashflow_service._asset_position`：新体系优先、旧表回落）"""
    from . import ratio_service
    return ratio_service


def _month_seq(ym_key: int) -> int:
    """`202503` → 连续月序（2025*12+3）。序列键是**整数 ym_key**，不是 'YYYY-MM'。"""
    ym_key = int(ym_key)
    return (ym_key // 100) * 12 + (ym_key % 100)


def _missing_months(keys):
    """两期之间被跳过的自然月（不连续盘点）"""
    missing = []
    for prev, cur in zip(keys, keys[1:]):
        for n in range(_month_seq(prev) + 1, _month_seq(cur)):
            missing.append(f'{n // 12}-{n % 12 or 12:02d}')
    return missing


def _flow(prev_date, cur_date, user_id):
    """区间 (prev_date, cur_date] 内的收支汇总，**按日期整天划界**"""
    start = timezone.make_aware(datetime.combine(prev_date + timedelta(days=1), time.min))
    end = timezone.make_aware(datetime.combine(cur_date + timedelta(days=1), time.min))

    qs = WealthBillList.objects.filter(
        user_id=user_id, date__gte=start, date__lt=end,
    )
    agg = qs.aggregate(
        income=Sum('amount', filter=Q(transaction_type=INCOME)),
        expense=Sum('amount', filter=Q(transaction_type=EXPENSE)),
        adjust=Sum('amount', filter=Q(transaction_type=ADJUST)),
    )
    return {
        'income': _r2(agg['income']),
        'expense': _r2(agg['expense']),
        'adjustment': _r2(agg['adjust']),
        'bill_count': qs.count(),
    }


def _period(prev, cur, user_id):
    """一期归因。`snapshot_date` 缺失时只给净值变化，不给流量（不猜窗口）"""
    from_date = prev.get('snapshot_date')
    to_date = cur.get('snapshot_date')

    assets_start, assets_end = _f(prev.get('total_assets')), _f(cur.get('total_assets'))
    borrow_start, borrow_end = _f(prev.get('borrow')), _f(cur.get('borrow'))
    net_start, net_end = _f(prev.get('net_worth')), _f(cur.get('net_worth'))

    row = {
        'from_yearmon': prev.get('yearmon'),
        'to_yearmon': cur.get('yearmon'),
        'from_date': from_date,
        'to_date': to_date,
        'days': (to_date - from_date).days if from_date and to_date else None,
        'assets_start': _r2(assets_start),
        'assets_end': _r2(assets_end),
        'assets_change': _r2(assets_end - assets_start),
        'borrow_start': _r2(borrow_start),
        'borrow_end': _r2(borrow_end),
        'borrow_change': _r2(borrow_end - borrow_start),
        'net_worth_start': _r2(net_start),
        'net_worth_end': _r2(net_end),
        'net_worth_change': _r2(net_end - net_start),
        'income': None,
        'expense': None,
        'adjustment': None,
        'flow_net': None,
        'bill_count': None,
        'unexplained': None,
        'unexplained_pct': None,
        'unexplained_side': None,
        'window_reason': 'ok',
        'level': 'no_window',
    }

    if not from_date or not to_date:
        row['window_reason'] = 'undated'       # 盘点没填日期 ⇒ 无法划窗口
        return row
    if to_date <= from_date:
        row['window_reason'] = 'invalid_span'  # 同月两次盘点且日期倒挂
        return row

    flow = _flow(from_date, to_date, user_id)
    flow_net = _r2(flow['income'] - flow['expense'] + flow['adjustment'])
    unexplained = _r2((assets_end - assets_start) - flow_net)

    row.update({
        'income': flow['income'],
        'expense': flow['expense'],
        'adjustment': flow['adjustment'],
        'flow_net': flow_net,
        'bill_count': flow['bill_count'],
        'unexplained': unexplained,
        'unexplained_pct': round(unexplained / abs(assets_start) * 100, 2) if assets_start else None,
        # 方向本身就是判据：正 = 钱多了但账本没记进项；负 = 钱少了但账本没记出项
        'unexplained_side': None if abs(unexplained) < 0.01 else (
            'more_than_recorded' if unexplained > 0 else 'less_than_recorded'
        ),
    })
    # 「需不需要看一眼」只在后端判：绝对值门槛，避免小额噪声天天空报警
    row['level'] = 'material' if abs(unexplained) >= BRIDGE_MATERIAL_AMOUNT else 'ok'
    return row


def _identity_ok(row) -> bool:
    """恒等式自检：Δ净资产 = 账本净流量 + 未解释差额 − Δ负债

    算不出来（无窗口）的期次直接放过 —— 这条只在有完整数据时才有意义。
    """
    if row['window_reason'] != 'ok':
        return True
    rebuilt = row['flow_net'] + row['unexplained'] - row['borrow_change']
    return abs(rebuilt - row['net_worth_change']) < 0.02


def build_networth_bridge(limit: int = 12, user_id: int = 1) -> dict:
    """近 N 期净资产变动归因（按年月升序返回，`latest` 是最后一期）"""
    series = _asset_position().resolve_asset_series(user_id) or {}
    keys = sorted(series)
    missing = _missing_months(keys)

    ordered = [series[k] for k in keys]
    periods = [
        _period(prev, cur, user_id)
        for prev, cur in zip(ordered, ordered[1:])
    ]
    if limit:
        periods = periods[-int(limit):]

    checkable = [p for p in periods if p['window_reason'] == 'ok']
    material = [p for p in checkable if p['level'] == 'material']

    latest = periods[-1] if periods else None
    stale_days = None
    if ordered:
        last_date = ordered[-1].get('snapshot_date')
        if last_date:
            stale_days = (timezone.localdate() - last_date).days

    return {
        'as_of': ordered[-1].get('yearmon') if ordered else None,
        'periods': periods,
        'latest': latest,
        'summary': {
            'periods': len(periods),
            'checkable': len(checkable),
            'material': len(material),
            'total_unexplained': _r2(sum(p['unexplained'] or 0 for p in checkable)),
            'missing_months': missing,
            'missing_count': len(missing),
            'stale_days': stale_days,
            'snapshot_count': len(keys),
            'identity_ok': all(_identity_ok(p) for p in periods),
        },
        'thresholds': {'material_amount': BRIDGE_MATERIAL_AMOUNT},
    }
