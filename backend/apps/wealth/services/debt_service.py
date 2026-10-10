"""负债明细 / 应收账龄服务 — 逐笔台账、还款优先级、账龄分布、快照对账

口径总则（与 wealth_cash_flow 快照的关系）：
    快照的 borrow / lend 是**每月盘点一次的汇总数**，本模块的台账是**逐笔明细**。
    两者不同步时**只报差额、不改数据** —— 快照是历史事实，不回溯篡改。
    对账差额 diff = 台账合计 − 快照值：正数表示台账比快照多（快照待更新或存在未入账的债）。

负债侧派生口径：
    已还本金     = 借款本金 − 剩余本金（不为负）
    年利息成本   = 剩余本金 × 年利率 ÷ 100（单利近似，不含还款计划与复利）
    加权平均利率 = Σ(剩余本金 × 年利率) ÷ Σ剩余本金 —— **权重是余额不是笔数**，
                   直接用笔数取算术平均会高估小额高息债的影响
    还款优先级   雪崩法 = 利率降序（省息最优）；雪球法 = 余额升序（心理最优）
                   ⚠️ 只对「在还」编号，已结清的优先级为 null

应收侧派生口径：
    未收回余额 = max(借出本金 − 已收回, 0)
    账龄天数   = 今天 − 借出日（分桶边界唯一定义在 constants.RECEIVABLE_AGING_BUCKETS）
    逾期       = 状态「在借」且约定期 < 今天；约定还款日为空则不做逾期判定（无依据）
    呆账       单列，计入未收回余额但不计入「在借」
"""

from datetime import date
from math import ceil

from apps.wealth.constants import (
    AGING_UNKNOWN_BUCKET,
    LONG_AGING_DAYS,
    RECEIVABLE_AGING_BUCKETS,
)
from apps.wealth.models import WealthLiabilityDetail, WealthReceivableDetail

from .cashflow_service import get_cashflow_overview

ACTIVE_LIABILITY = '在还'
ACTIVE_RECEIVABLE = '在借'
BAD_DEBT = '呆账'


def _round(value: float | None, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def aging_bucket(days: int | None) -> str:
    """账龄天数 → 桶名。

    借出日为空（days=None）归入「未填借出日」，**默认落 0 天桶是把「没数据」当「刚借出」**。
    借出日晚于今天（days<0）属录入错误，同样不归桶。
    """
    if days is None or days < 0:
        return AGING_UNKNOWN_BUCKET
    for start, end, label in RECEIVABLE_AGING_BUCKETS:
        if days >= start and (end is None or days <= end):
            return label
    return RECEIVABLE_AGING_BUCKETS[-1][2]


# ══════════════════════════════════════════════════════════════
# 负债明细
# ══════════════════════════════════════════════════════════════


def _liability_item(obj: WealthLiabilityDetail, rank_rate: int | None,
                    rank_balance: int | None, today: date) -> dict:
    outstanding = _round(obj.outstanding)
    principal = _round(obj.principal)
    rate = _round(obj.annual_rate)
    monthly = _round(obj.monthly_payment)
    return {
        'id': obj.id,
        'name': obj.name,
        'category': obj.category,
        'principal': principal,
        'outstanding': outstanding,
        'annual_rate': rate,
        'start_date': str(obj.start_date) if obj.start_date else None,
        'due_date': str(obj.due_date) if obj.due_date else None,
        'repayment_method': obj.repayment_method,
        'monthly_payment': monthly,
        'status': obj.status,
        'remark': obj.remark or '',
        'repaid_amount': _round(max(principal - outstanding, 0)),
        'repaid_ratio': _round((principal - outstanding) / principal * 100, 1) if principal > 0 else 0.0,
        'annual_interest_cost': _round(outstanding * rate / 100),
        # 剩余期数：按月供平摊的估算值（非还款计划表），月供为 0 时无依据 → null
        'remaining_months': ceil(outstanding / monthly) if (monthly > 0 and outstanding > 0) else None,
        'days_to_due': (obj.due_date - today).days if obj.due_date else None,
        'priority_by_rate': rank_rate,
        'priority_by_balance': rank_balance,
        'created_at': obj.created_at.isoformat() if obj.created_at else None,
        'updated_at': obj.updated_at.isoformat() if obj.updated_at else None,
    }


def get_liability_list(user_id: int = 1) -> list[dict]:
    """负债明细列表：在还按利率降序（雪崩法序）在前，已结清在后"""
    today = date.today()
    objs = list(WealthLiabilityDetail.objects.filter(user_id=user_id).order_by('id'))

    active = [o for o in objs if o.status == ACTIVE_LIABILITY]
    # 并列时用 id 兜底，保证同一批数据的优先级稳定可复现
    by_rate = sorted(active, key=lambda o: (-(o.annual_rate or 0), o.id))
    by_balance = sorted(active, key=lambda o: (o.outstanding or 0, o.id))
    rank_rate = {o.id: i + 1 for i, o in enumerate(by_rate)}
    rank_balance = {o.id: i + 1 for i, o in enumerate(by_balance)}

    ordered = by_rate + [o for o in objs if o.status != ACTIVE_LIABILITY]
    return [_liability_item(o, rank_rate.get(o.id), rank_balance.get(o.id), today) for o in ordered]


def get_liability_summary(user_id: int = 1) -> dict:
    """负债汇总：余额、月供、加权平均利率、分类分布、与快照 borrow 的对账差"""
    today = date.today()
    items = get_liability_list(user_id)
    active = [i for i in items if i['status'] == ACTIVE_LIABILITY]

    total_principal = sum(i['principal'] for i in items)
    total_outstanding = sum(i['outstanding'] for i in active)
    total_monthly = sum(i['monthly_payment'] for i in active)
    annual_interest = sum(i['annual_interest_cost'] for i in active)

    # 加权平均利率：权重为剩余本金
    weighted = (
        sum(i['outstanding'] * i['annual_rate'] for i in active) / total_outstanding
        if total_outstanding > 0 else 0.0
    )

    # 分类分布（金额口径为在还剩余本金）
    buckets: dict[str, dict] = {}
    for i in active:
        b = buckets.setdefault(i['category'], {'count': 0, 'outstanding': 0.0, 'monthly_payment': 0.0})
        b['count'] += 1
        b['outstanding'] += i['outstanding']
        b['monthly_payment'] += i['monthly_payment']
    by_category = [
        {
            'category': k,
            'count': v['count'],
            'outstanding': _round(v['outstanding']),
            'monthly_payment': _round(v['monthly_payment']),
            'share': _round(v['outstanding'] / total_outstanding * 100, 1) if total_outstanding > 0 else 0.0,
        }
        for k, v in sorted(buckets.items(), key=lambda kv: -kv[1]['outstanding'])
    ]

    highest = max(active, key=lambda i: i['annual_rate'], default=None)
    focus_rate = sorted(active, key=lambda i: (-i['annual_rate'], i['id']))[0] if active else None
    focus_balance = sorted(active, key=lambda i: (i['outstanding'], i['id']))[0] if active else None

    return {
        'as_of': str(today),
        'count': len(items),
        'active_count': len(active),
        'settled_count': len(items) - len(active),
        'total_principal': _round(total_principal),
        'total_outstanding': _round(total_outstanding),
        'total_monthly_payment': _round(total_monthly),
        'weighted_avg_rate': _round(weighted),
        'highest_rate_item': (
            {'name': highest['name'], 'annual_rate': highest['annual_rate']} if highest else None
        ),
        'annual_interest_cost': _round(annual_interest),
        'by_category': by_category,
        # 「先还哪一笔」的答案：两种策略各给首笔，差异即策略差异
        'prepay_focus': {
            'by_rate': focus_rate['name'] if focus_rate else None,
            'by_balance': focus_balance['name'] if focus_balance else None,
        },
        **_borrow_reconcile(total_outstanding),
    }


def _borrow_reconcile(ledger_total: float) -> dict:
    """台账合计 vs 最新快照的 borrow"""
    overview = get_cashflow_overview() or {}
    snapshot = (overview.get('summary') or {}).get('borrow')
    if snapshot is None:
        return {'snapshot_borrow': None, 'borrow_diff': None}
    return {
        'snapshot_borrow': _round(snapshot),
        'borrow_diff': _round(ledger_total - snapshot),
    }


# ══════════════════════════════════════════════════════════════
# 应收借出明细
# ══════════════════════════════════════════════════════════════


def _receivable_item(obj: WealthReceivableDetail, today: date) -> dict:
    principal = _round(obj.principal)
    received = _round(obj.received)
    rate = _round(obj.annual_rate)
    outstanding = _round(max(principal - received, 0))

    aging_days = (today - obj.lend_date).days if obj.lend_date else None
    is_active = obj.status == ACTIVE_RECEIVABLE
    overdue_days = (
        (today - obj.due_date).days if (is_active and obj.due_date and obj.due_date < today) else 0
    )
    return {
        'id': obj.id,
        'counterparty': obj.counterparty,
        'principal': principal,
        'received': received,
        'outstanding': outstanding,
        'recovery_ratio': _round(received / principal * 100, 1) if principal > 0 else 0.0,
        'lend_date': str(obj.lend_date) if obj.lend_date else None,
        'due_date': str(obj.due_date) if obj.due_date else None,
        'annual_rate': rate,
        'status': obj.status,
        'remark': obj.remark or '',
        'aging_days': aging_days,
        'aging_bucket': aging_bucket(aging_days),
        'is_long_aging': bool(aging_days is not None and aging_days >= LONG_AGING_DAYS and is_active),
        'is_overdue': overdue_days > 0,
        'overdue_days': overdue_days,
        'annual_interest_income': _round(outstanding * rate / 100),
        'created_at': obj.created_at.isoformat() if obj.created_at else None,
        'updated_at': obj.updated_at.isoformat() if obj.updated_at else None,
    }


def get_receivable_list(user_id: int = 1) -> list[dict]:
    """应收借出列表：在借按账龄降序（越久越靠前）在前，其余按借出日倒序"""
    today = date.today()
    objs = list(WealthReceivableDetail.objects.filter(user_id=user_id).order_by('id'))
    items = [_receivable_item(o, today) for o in objs]

    active = [i for i in items if i['status'] == ACTIVE_RECEIVABLE]
    # 账龄未知的排在最后：有数据的优先显示
    active.sort(key=lambda i: (-(i['aging_days'] if i['aging_days'] is not None else -1), i['id']))
    others = [i for i in items if i['status'] != ACTIVE_RECEIVABLE]
    others.sort(key=lambda i: (i['lend_date'] or '', i['id']), reverse=True)
    return active + others


def get_receivable_summary(user_id: int = 1) -> dict:
    """应收汇总：未收回、回收率、账龄分布、逾期、无息占比、与快照 lend 的对账差"""
    today = date.today()
    items = get_receivable_list(user_id)
    active = [i for i in items if i['status'] == ACTIVE_RECEIVABLE]
    bad = [i for i in items if i['status'] == BAD_DEBT]

    total_lent = sum(i['principal'] for i in items)
    total_received = sum(i['received'] for i in items)
    active_outstanding = sum(i['outstanding'] for i in active)
    bad_debt_amount = sum(i['outstanding'] for i in bad)
    total_outstanding = active_outstanding + bad_debt_amount

    overdue = [i for i in active if i['is_overdue']]
    interest_free = sum(i['outstanding'] for i in active if i['annual_rate'] == 0)

    # 账龄分布：桶固定 5 段 + 「未填借出日」，份额合计恒为 100%
    counts: dict[str, dict] = {
        label: {'count': 0, 'amount': 0.0} for _, _, label in RECEIVABLE_AGING_BUCKETS
    }
    counts[AGING_UNKNOWN_BUCKET] = {'count': 0, 'amount': 0.0}
    for i in active:
        b = counts.setdefault(i['aging_bucket'], {'count': 0, 'amount': 0.0})
        b['count'] += 1
        b['amount'] += i['outstanding']
    aging = [
        {
            'bucket': label,
            'count': v['count'],
            'amount': _round(v['amount']),
            'share': _round(v['amount'] / active_outstanding * 100, 1) if active_outstanding > 0 else 0.0,
        }
        for label, v in counts.items()
    ]

    return {
        'as_of': str(today),
        'count': len(items),
        'active_count': len(active),
        'bad_debt_count': len(bad),
        'total_lent': _round(total_lent),
        'total_received': _round(total_received),
        'total_outstanding': _round(total_outstanding),
        'active_outstanding': _round(active_outstanding),
        'bad_debt_amount': _round(bad_debt_amount),
        'recovery_ratio': _round(total_received / total_lent * 100, 1) if total_lent > 0 else 0.0,
        'overdue_count': len(overdue),
        'overdue_amount': _round(sum(i['outstanding'] for i in overdue)),
        'max_overdue_days': max((i['overdue_days'] for i in overdue), default=0),
        'long_aging_count': len([i for i in active if i['is_long_aging']]),
        'interest_income_annual': _round(sum(i['annual_interest_income'] for i in active)),
        'interest_free_amount': _round(interest_free),
        'interest_free_ratio': (
            _round(interest_free / active_outstanding * 100, 1) if active_outstanding > 0 else 0.0
        ),
        'aging': aging,
        **_lend_reconcile(total_outstanding),
    }


def _lend_reconcile(ledger_total: float) -> dict:
    """台账合计 vs 最新快照的 lend"""
    overview = get_cashflow_overview() or {}
    snapshot = (overview.get('summary') or {}).get('lend')
    if snapshot is None:
        return {'snapshot_lend': None, 'lend_diff': None}
    return {
        'snapshot_lend': _round(snapshot),
        'lend_diff': _round(ledger_total - snapshot),
    }
