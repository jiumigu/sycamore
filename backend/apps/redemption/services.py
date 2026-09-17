"""三年赎回期 · 核心计算服务

所有 money 侧统计走 WealthBillList（managed=False 外部表），time 侧走 TemporalTask
（managed=False 外部表），归因通过 RedemptionAttrRule 外挂映射，绝不向这两张表加列。
同步推演复用 apps.wealth 既有 calculate_coverage，不覆盖用户的长期推演起点。
"""
from datetime import date, datetime, timedelta

from django.db.models import Case, Sum, When
from django.db.models.functions import Cast
from django.db.models import DateField, DecimalField, F, Q, Value

# 覆盖率分母：每天醒来 16h − 生存 4h = 12h 可支配（暂定，可改实测基准）
THEORETICAL_DAILY_HOURS = 12
# 单位赎回成本分母：12h/天 − 上班 4h/天 = 净增 8h/天
REDEEMED_DAILY_HOURS = 8
# 覆盖率低于该值给出「仅基于已记录部分，谨慎解读」提示
COVERAGE_WARN_THRESHOLD = 0.5

PERIOD_TAG_CHOICES = ['为自己', '过渡', '外部', '不计入']
ATTRIBUTION_CHOICES = ['投向', '维持', '外部', '流失']


def get_or_create_period():
    from .models import RedemptionPeriod
    period, _ = RedemptionPeriod.objects.get_or_create(
        pk=1,
        defaults={
            'start_date': date(2026, 10, 1),
            'end_date': date(2029, 9, 30),
            'pool_principal': 100000,
            'tracking_status': 'active',
        },
    )
    return period


def _window_bounds(period):
    """返回窗口 [start_dt, end_dt] 的 datetime 边界，规避 USE_TZ 下 __date 的 CONVERT_TZ 坑。"""
    start_dt = datetime.combine(period.start_date, datetime.min.time())
    end_dt = datetime.combine(period.end_date, datetime.max.time())
    return start_dt, end_dt


def _today_clamped(period):
    return min(date.today(), period.end_date)


def compute_pool_balance(period):
    """B2 启动现金池余额 = 本金 + 累计注入 − 为自己净消耗(支出−收入)。"""
    from apps.wealth.models import WealthBillList
    from .models import RedemptionPoolInject

    inject_total = RedemptionPoolInject.objects.aggregate(
        s=Sum('amount')
    )['s'] or 0

    start_dt, end_dt = _window_bounds(period)
    agg = WealthBillList.objects.filter(
        user_id=1, period_tag='为自己', date__gte=start_dt, date__lte=end_dt,
    ).aggregate(
        expense=Sum(Case(When(transaction_type='支出', then=F('amount')), default=Value(0),
                         output_field=DecimalField(max_digits=14, decimal_places=2))),
        income=Sum(Case(When(transaction_type='收入', then=F('amount')), default=Value(0),
                        output_field=DecimalField(max_digits=14, decimal_places=2))),
    )
    self_expense = float(agg['expense'] or 0)
    self_income = float(agg['income'] or 0)
    balance = float(period.pool_principal) + float(inject_total) - self_expense + self_income
    return {
        'principal': float(period.pool_principal),
        'injected': float(inject_total),
        'self_expense': round(self_expense, 2),
        'self_income': round(self_income, 2),
        'balance': round(balance, 2),
    }


def compute_avg_daily_self_net(period, days=30):
    """滚动 N 天「为自己」净消耗均值（支出−收入）/ N，作为同步推演的 daily_budget。"""
    from apps.wealth.models import WealthBillList

    cutoff = datetime.combine(date.today() - timedelta(days=days), datetime.min.time())
    start_dt, end_dt = _window_bounds(period)
    lo = max(cutoff, start_dt)
    agg = WealthBillList.objects.filter(
        user_id=1, period_tag='为自己', date__gte=lo, date__lte=end_dt,
    ).aggregate(
        net=Sum(Case(
            When(transaction_type='支出', then=F('amount')),
            When(transaction_type='收入', then=-F('amount')),
            default=Value(0),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )),
    )
    net = float(agg['net'] or 0)
    return round(net / days, 2)


def compute_support_until(period, pool_balance):
    """按当前余额与滚动日均净消耗，估算可支撑到哪天（avg<=0 → 永不耗尽）。"""
    avg_daily = compute_avg_daily_self_net(period)
    if avg_daily <= 0:
        return None
    days_left = int(pool_balance / avg_daily)
    return (date.today() + timedelta(days=days_left)).isoformat()


def compute_tier_stats(period):
    """窗口内按四档 + 未标记 分组笔数/金额（收入支出合计）。"""
    from apps.wealth.models import WealthBillList

    start_dt, end_dt = _window_bounds(period)
    rows = (
        WealthBillList.objects
        .filter(user_id=1, date__gte=start_dt, date__lte=end_dt)
        .values('period_tag')
        .annotate(cnt=Sum('id'), total=Sum('amount'))
    )
    bucket = {n: {'count': 0, 'total': 0.0} for n in (*PERIOD_TAG_CHOICES, 'unmarked')}
    for r in rows:
        n = r['period_tag'] or ''
        key = n if n in bucket else 'unmarked'
        bucket[key]['count'] = r['cnt'] or 0
        bucket[key]['total'] = round(float(r['total'] or 0), 2)
    return [
        {'period_tag': k, 'count': v['count'], 'total': v['total']}
        for k, v in bucket.items()
    ]


def _match_attribution(task, rules_index):
    """按优先级匹配一条归因规则，返回归因类别或 None。"""
    best = None
    for rule in rules_index:
        val = getattr(task, rule.match_field, None)
        if val is None:
            continue
        if str(val) == rule.match_value:
            if best is None or rule.priority > best.priority:
                best = rule
    return best.attribution if best else None


def compute_time_attribution(period):
    """窗口内 ATracker 任务经外挂规则映射后的四类小时 + 覆盖率。"""
    from apps.temporal.models import TemporalTask
    from .models import RedemptionAttrRule

    rules_index = list(RedemptionAttrRule.objects.filter(is_active=True))
    start_dt, end_dt = _window_bounds(period)

    tasks = TemporalTask.objects.filter(
        start_time__gte=start_dt, start_time__lte=end_dt,
    )
    hours = {k: 0.0 for k in ATTRIBUTION_CHOICES}
    covered = 0.0
    for t in tasks:
        attr = _match_attribution(t, rules_index)
        h = float(t.duration_hours or 0)
        if attr and h:
            hours[attr] += h
            covered += h

    today = _today_clamped(period)
    days_elapsed = (today - period.start_date).days + 1
    days_elapsed = max(days_elapsed, 0)
    theoretical = days_elapsed * THEORETICAL_DAILY_HOURS
    coverage_rate = round(covered / theoretical, 4) if theoretical else 0.0
    toward_ratio = round(hours['投向'] / covered, 4) if covered else 0.0

    return {
        'hours': {k: round(v, 2) for k, v in hours.items()},
        'covered_hours': round(covered, 2),
        'theoretical_hours': round(theoretical, 2),
        'coverage_rate': coverage_rate,
        'coverage_warn': coverage_rate < COVERAGE_WARN_THRESHOLD,
        'toward_ratio': toward_ratio,
        'days_elapsed': days_elapsed,
    }


def compute_unit_cost(period):
    """单位赎回成本 = 为自己净消耗 / 净赎回小时（elapsed_days × 8h）。"""
    pool = compute_pool_balance(period)
    today = _today_clamped(period)
    elapsed_days = (today - period.start_date).days + 1
    elapsed_days = max(elapsed_days, 0)
    redeemed_hours = elapsed_days * REDEEMED_DAILY_HOURS
    net_self = pool['self_expense'] - pool['self_income']
    if redeemed_hours <= 0:
        return None
    return round(net_self / redeemed_hours, 2)


def compute_redemption_stats(period, include_time=True):
    """合体统计，供仪表盘消费。"""
    today = _today_clamped(period)
    total_days = (period.end_date - period.start_date).days + 1
    elapsed_days = (today - period.start_date).days + 1
    elapsed_days = max(elapsed_days, 0)

    pool = compute_pool_balance(period)
    support_until = compute_support_until(period, pool['balance'])
    tier = compute_tier_stats(period)
    stats = {
        'window': {
            'start': period.start_date.isoformat(),
            'end': period.end_date.isoformat(),
            'total_days': total_days,
            'elapsed_days': elapsed_days,
            'remaining_days': max(total_days - elapsed_days, 0),
        },
        'tracking_status': period.tracking_status,
        'pool': {**pool, 'avg_daily': compute_avg_daily_self_net(period), 'support_until': support_until},
        'tier': tier,
    }
    if include_time and period.tracking_status == 'active':
        stats['time'] = compute_time_attribution(period)
        stats['unit_cost'] = compute_unit_cost(period)
    else:
        stats['time'] = None
        stats['unit_cost'] = None
    return stats


def sync_to_scenario(period, mode='preview'):
    """把赎回池实算值同步到 WealthCurrentScenario（复用 calculate_coverage）。

    preview：只返回推演结果，不写库；apply：写入 current_cash/daily_budget 并重算
    support_weeks/end_age/end_week + 写 WealthScenarioHistory。
    start_age/start_week 取既有推演当前位置，不覆盖用户的长期推演。
    """
    from apps.wealth.models import WealthCurrentScenario, WealthScenarioHistory
    from apps.wealth.services.coverage_calculator import calculate_coverage

    pool = compute_pool_balance(period)
    avg_daily = compute_avg_daily_self_net(period)
    scenario = WealthCurrentScenario.objects.first()
    if scenario is None:
        # 推演单例行尚未建立：preview/apply 都不写库，只告知
        return {
            'mode': mode,
            'scenario_exists': False,
            'cash': round(float(pool['balance']), 2),
            'daily_budget': avg_daily,
            'support_weeks': None,
            'end_age': None,
            'end_week': None,
        }

    coverage, support_weeks, end_age, end_week = calculate_coverage(
        start_age=scenario.current_age,
        start_week=scenario.current_week,
        cash=float(pool['balance']),
        daily_budget=float(avg_daily),
    )
    result = {
        'mode': mode,
        'scenario_exists': True,
        'cash': round(float(pool['balance']), 2),
        'daily_budget': avg_daily,
        'support_weeks': support_weeks,
        'end_age': end_age,
        'end_week': end_week,
    }

    if mode == 'apply':
        scenario.current_cash = pool['balance']
        scenario.daily_budget = avg_daily
        scenario.support_weeks = support_weeks if support_weeks is not None else 9999
        scenario.end_age = end_age
        scenario.end_week = end_week
        scenario.save()
        WealthScenarioHistory.objects.create(
            current_age=scenario.current_age,
            current_week=scenario.current_week,
            current_cash=pool['balance'],
            daily_budget=avg_daily,
            support_weeks=scenario.support_weeks,
            note='三年赎回期同步',
        )
    return result
