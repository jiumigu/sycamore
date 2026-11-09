"""赎回期 · 核心计算函数（**无模型、无端点、无单例**）

2026-11-02 起本模块只提供**按区间算数**的纯函数，供自我运转的阶段账本复用
（`selfrun.services.stage_ledger`）。「三年赎回期」已经不是模块，而是自我运转下的
一个长阶段 —— 所以这里不再有「赎回期配置」「暂停追踪」「同步到推演」这些概念，
也不认任何单例（`get_or_create_period` 已删）。

所有 money 侧统计走 WealthBillList（managed=False 外部表），time 侧走 TemporalTask
（managed=False 外部表）。归因**不由本模块自管**：一律复用
`temporal.services.resolve_attribution_detail`（映射表那列），绝不向这两张表加列。

🔴 每个函数都吃**显式区间** `(start, end)`，不吃对象：
   同一个量两个入口，半年后没人知道该用哪个。
"""
from datetime import date, datetime, timedelta

from django.db.models import Case, Count, DecimalField, F, Sum, Value, When

# ⚠️ 归因词表**单一真源**在 apps.temporal.constants（v3.58.10 起收敛）。
#    此处曾各存一份副本，导致改词要同时动 3 个地方、极易漂移。禁止在本文件重新定义。
# ⚠️ 注意两者形状不同：ATTRIBUTION_CHOICES 是 (值, 显示名) 元组对（给 Django choices 用），
#    ATTRIBUTION_CHOICES_LIST 才是纯值字符串列表。本模块只需要值，故取后者 ——
#    曾因误用前者导致 hours 字典的 key 变成 tuple，JSON 序列化直接 TypeError。
from apps.temporal.constants import ATTRIBUTION_CHOICES_LIST, PERIOD_TAG_CHOICES

# 覆盖率分母：每天醒来 16h − 生存 2h = 14h 可支配（2026-11-05 用户把 12h 调到 14h）
THEORETICAL_DAILY_HOURS = 14
# 单位赎回成本分母：原推导「12h/天 − 上班 4h/天 = 净增 8h/天」。
# ⚠️ 2026-11-05 可支配已调到 14h ⇒ 这条推导**不再成立**；该常量现在只剩
#    `compute_unit_cost()` 在用（阶段账本 v3.64.24 起已不展示 ¥/h，见 CHANGELOG）。
#    要改它先想清楚「净赎回小时」到底指什么，别顺手跟着 14−4=10 一起改。
REDEEMED_DAILY_HOURS = 8
# 覆盖率低于该值给出「仅基于已记录部分，谨慎解读」提示
COVERAGE_WARN_THRESHOLD = 0.5


def _window_bounds(start, end):
    """区间 `[start 00:00, end+1天 00:00)` 的 datetime 边界。

    🔴 **半开区间**（项目铁律四）：`USE_TZ=True` 下 `__date` 会走 `CONVERT_TZ`，
       而 `__lte=datetime.max.time()` 在微秒上是个「几乎含、实际漏」的边界。
       半开只用一个方向（`__lt`），终点那天的 23:59 记录不会漏。
    🔴 参数是 `date`，不是 `period` —— 2026-11-02 起本模块的计算函数吃显式区间，
       好让自我运转的**任意阶段**复用同一份口径（`selfrun.services.stage_ledger`）。
       不留「还能吃 period」的兼容分支：同一个量两个入口，半年后没人知道该用哪个。
    """
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())
    return start_dt, end_dt


def compute_pool_balance(principal, start, end, injected=0.0, exclude_bill_ids=()):
    """现金池余额 = 本金 + 区间内注入 − 为自己净消耗(支出−收入)。

    🔴 **注入与消耗按同一个窗口过滤**（2026-11-02 修正）：旧实现只把消耗夹在窗口内、
       注入却取全表求和 —— 对单例赎回期看不出问题（窗口就是全部历史），
       但阶段账本会因此把 A 阶段的注水算进 B 阶段的余额（静默、且数看着很合理）。
       v3.64.20 起注入由**调用方按阶段归属**算好传入（`selfrun_pool_inject.stage`），
       本函数不查任何注入表 —— 它连模型都不 import，才可能被任意阶段复用。
       ⚠️ v3.64.26 起注入改为「标记账单」，窗口由调用方按同一区间夹好
          （`selfrun.readers.pool_inject_totals`），本函数的契约没变。
    🔴 `exclude_bill_ids`（2026-11-05 追加）：被标为注入的收入**必须从净消耗里排除**。
       否则那笔钱既加进 `injected`、又通过 `self_income` 减少净消耗，
       余额凭空多出一倍 —— 而且页面上下两个数各自看着都合理。
    ⚠️ `principal` 同理由调用方给（阶段取 `ledger_config['pool_principal']`）。
    """
    from apps.wealth.models import WealthBillList

    start_dt, end_dt = _window_bounds(start, end)
    bills = WealthBillList.objects.filter(
        user_id=1, period_tag='为自己', date__gte=start_dt, date__lt=end_dt,
    )
    exclude = list(exclude_bill_ids or ())
    if exclude:
        bills = bills.exclude(id__in=exclude)
    agg = bills.aggregate(
        expense=Sum(Case(When(transaction_type='支出', then=F('amount')), default=Value(0),
                         output_field=DecimalField(max_digits=14, decimal_places=2))),
        income=Sum(Case(When(transaction_type='收入', then=F('amount')), default=Value(0),
                        output_field=DecimalField(max_digits=14, decimal_places=2))),
    )
    self_expense = float(agg['expense'] or 0)
    self_income = float(agg['income'] or 0)
    inject_total = float(injected or 0)
    balance = float(principal) + inject_total - self_expense + self_income
    return {
        'principal': float(principal),
        'injected': round(inject_total, 2),
        'self_expense': round(self_expense, 2),
        'self_income': round(self_income, 2),
        'balance': round(balance, 2),
    }


def compute_avg_daily_self_net_detail(start, end, days=30):
    """滚动 N 天口径的**完整读数**：`avg_daily` + 窗口实际覆盖天数。

    🔴 **分母 = `min(窗口实际天数, days)`**（2026-11-09 定口径，用户认可）。
       旧实现固定除 `days`（30）：阶段第 5 天时 ¥1,142 摊到 30 天读成「每天 ¥38」，
       而实际是 ¥229/天 —— 差 6 倍，且「撑到哪天」凭空乐观 4 年多
       （38 撑到 2030-11，229 撑到 2028-01）。分母不摊薄之后，
       **满 30 天后数值与旧口径完全相同**，只有阶段头 29 天会变（变对）。
    🔴 `sample_days < days` ⇒ `thin`：样本不足 30 天，速度可能还没经历月末大额，
       `support_until` 仍可能偏乐观。调用方必须把 `sample_days` 摆到页面上。
       「样本短」现在是**提示**，不再是「数被稀释」的补丁。
    🔴 锚点是 `min(今天, 终点)`：已归档的阶段按**它收尾那天**往回滚 30 天，
       不能按今天 —— 否则拿归档三个月后的账去算它当时的日均。
    """
    from apps.wealth.models import WealthBillList

    anchor = min(date.today(), end)
    if anchor < start:
        return {'avg_daily': 0.0, 'sample_days': 0, 'thin': True}
    lo = max(anchor - timedelta(days=days), start)
    # 窗口是半开区间 [lo 00:00, anchor+1天 00:00) ⇒ 含 anchor 当天；上限夹到 days，
    # 免得「anchor−30 天」这种取法因含两端算出 31 天、与分母 30 打架。
    sample_days = min((anchor - lo).days + 1, days)
    start_dt, end_dt = _window_bounds(lo, anchor)
    agg = WealthBillList.objects.filter(
        user_id=1, period_tag='为自己', date__gte=start_dt, date__lt=end_dt,
    ).aggregate(
        net=Sum(Case(
            When(transaction_type='支出', then=F('amount')),
            When(transaction_type='收入', then=-F('amount')),
            default=Value(0),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )),
    )
    net = float(agg['net'] or 0)
    return {
        # 分母是**实际覆盖天数**，不是写死的 30 —— 见 docstring
        'avg_daily': round(net / sample_days, 2) if sample_days else 0.0,
        'sample_days': sample_days,
        'thin': sample_days < days,
    }


def compute_avg_daily_self_net(start, end, days=30):
    """滚动 N 天「为自己」净消耗均值（支出−收入）/ **实际覆盖天数**（≤ N），
    作为同步推演的 daily_budget。

    ⚠️ 只是 `compute_avg_daily_self_net_detail` 的均值那一项 —— 口径只此一份，
       需要样本天数 / 真实日均的调用方请直接用 `_detail`，别在这上面再除一次。
    """
    return compute_avg_daily_self_net_detail(start, end, days)['avg_daily']


def compute_support_until(balance, avg_daily, anchor=None):
    """按当前余额与日均净消耗估算能撑到哪天 → `(日期字符串|None, zero_reason|None)`。

    🔴 **`avg_daily <= 0` 不是「永不耗尽」**（2026-11-02 修正）。
       旧实现返回 `None`，页面就印成「永不耗尽」—— 而 `None` 在别处到处代表
       「算不出来」。窗口刚开、还没有一条「为自己」的账时分母为 0，
       真实含义是「**还没有速度可外推**」，不是「钱花不完」。
       现在把原因显式交出去（`no_self_expense`），由前端查表给一句人话。
    🔴 **`0` 和负数不是一件事**（2026-11-05 修）：`avg_daily == 0` 是「没账可外推」，
       `avg_daily < 0` 是「净流入，钱在变多」—— 后者根本没有耗尽日。
       曾经两者共用 `no_self_expense`，于是页面上写着「这段路还没有一条『为自己』的账」，
       而同一屏的档位分布明明列着 16 笔（用户截图实证）。**说反话比不报更坏**。
    ⚠️ 余额为负时算出的日期落在过去 —— 那是事实（已经超支），照实给，不夹到今天。
    """
    anchor = anchor or date.today()
    if avg_daily < 0:
        return None, 'net_inflow'
    if avg_daily == 0:
        return None, 'no_self_expense'
    days_left = int(balance / avg_daily)
    return (anchor + timedelta(days=days_left)).isoformat(), None


def compute_tier_stats(start, end):
    """区间内按四档 + 未标记 分组笔数/金额（收入支出合计）。

    🔴 **笔数必须 `Count`，不能 `Sum('id')`**（2026-11-02 修正）。
       旧实现求「id 之和」当笔数：两条 id=5、9 的账单会显示成 **14 笔**。
       这个错**不会报错也不会离谱到被一眼看出**（账单 id 连续，量级相近），
       只是笔数整体偏大 —— 典型的「口径错给了一个看着合理的值」。
    ⚠️ 金额是收入与支出**直接相加**（不带符号），所以它是「发生额」而不是「净额」；
       别拿它和 `compute_pool_balance` 的 `self_expense − self_income` 对账。
    """
    from apps.wealth.models import WealthBillList

    start_dt, end_dt = _window_bounds(start, end)
    rows = (
        WealthBillList.objects
        .filter(user_id=1, date__gte=start_dt, date__lt=end_dt)
        .values('period_tag')
        .annotate(cnt=Count('id'), total=Sum('amount'))
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


def compute_time_attribution(start, end):
    """区间内 ATracker 任务 → 六类归因小时 + 覆盖率（**睡眠类已剔除**）。

    🔴 **分子与分母必须同口径：两边都不含睡眠**（2026-11-02 修正）。
       分母是「每天 14h 可支配」（`THEORETICAL_DAILY_HOURS`，2026-11-05 由 12h 调到 14h），
       睡眠本来就不在这 16h 醒来时间里。旧版分子却把睡眠算进去 ⇒ 记录越全、覆盖率越高，
       两天就冲到 **141.5%**，看上去像「记得比可支配的还多」。
       那不是记得多，是**口径错配**：同一屏上下两个数用了两把尺子。
       旧版还在界面写了一句「记录含睡眠，可能超过 100%」—— 那是给口径错配写的说明书，
       现在说明书写的东西已经不存在了。
    🔴 **剔除必须可见**：返回 `excluded_sleep_hours`。静默剔掉 12h 会让
       「维持」凭空少一块，而屏幕上没有任何线索说明它去了哪。
    🔴 **睡眠名单不在这里定义**（单一真源）：`temporal.services.contrib_excluded_names()`
       = 常量名单 ∪ 角色为睡眠类的任务。与贡献图同一份名单，否则账本说「维持 3.6h」、
       贡献图说「维持 15.8h」，两页都看着合理。
    ⚠️ 名单含**午睡**：午睡其实落在醒来那 16h 内，严格说可支配。但「睡眠时间」
       作为一个整体剔除更符合直觉，且与贡献图一致；代价是覆盖率略微保守
       （午睡那段被算成「没记录」）。页面把剔除小时数印在覆盖率下面，看得见。

    🔴 **只有一把尺子**：归因一律走 `temporal.services.resolve_attribution_detail`
       （映射表那列 `default_attribution`），与时间统计页 / 贡献图 / 每日护栏 /
       周复盘完全同源。本模块曾自有一套 `redemption_attr_rule` 外挂规则，
       2026-11-02 整体退役 —— 见下方「为什么」。
    🔴 **除睡眠外的全部记录都要落进六类**：没设默认归因的按兜底归因计入，并单独报
       `fallback_hours`。不能像从前那样「命中规则才算」。
    ⚠️ 为什么：旧口径下 2 天窗口（含睡眠）33.96h 只统计 20h（漏掉未配规则的任务名），
       「成长」1.99h 而真实 12.39h、「谋生」恒为 0，覆盖率显示 83% 看似完整。
       这种漏是**静默**的：不报错、不提示，只让读数偏低。

    ⚠️ `hours` 的键集由 `ATTRIBUTION_CHOICES_LIST` 派生 ⇒ 新增 L1 词自动跟随，
    本函数无需改动（v3.60.36 加「体验」时即是如此）。
    """
    from apps.temporal.models import TemporalTask
    from apps.temporal.services import contrib_excluded_names, resolve_attribution_detail

    start_dt, end_dt = _window_bounds(start, end)
    rows = list(
        TemporalTask.objects
        .filter(start_time__gte=start_dt, start_time__lt=end_dt)
        .values('task_name', 'duration_hours')
    )
    detail = resolve_attribution_detail(sorted({r['task_name'] for r in rows}))
    # 睡眠类名单（常量 ∪ 角色）—— 与贡献图同一个函数，不在这里另立一份
    excluded_names = contrib_excluded_names()

    hours = {k: 0.0 for k in ATTRIBUTION_CHOICES_LIST}
    covered = 0.0      # 已记录小时（= 分子；**不含睡眠**）
    fallback = 0.0     # 其中「没设默认归因、按兜底计入」的那部分
    excluded = 0.0     # 被剔除的睡眠小时（只是报出来，不进六类、不进分子）
    for r in rows:
        h = float(r['duration_hours'] or 0)
        if not h:
            continue
        if r['task_name'] in excluded_names:
            excluded += h
            continue
        d = detail.get(r['task_name']) or {}
        hours[d.get('attribution') or ATTRIBUTION_CHOICES_LIST[0]] += h
        covered += h
        if d.get('source') == 'fallback':
            fallback += h

    today = min(date.today(), end)
    days_elapsed = (today - start).days + 1
    days_elapsed = max(days_elapsed, 0)
    theoretical = days_elapsed * THEORETICAL_DAILY_HOURS
    coverage_rate = round(covered / theoretical, 4) if theoretical else 0.0
    # 占比 = 「成长」小时 / 已记录小时（对外字段名仍是 toward_ratio，见 README）
    # ⚠️ 分母**不含睡眠**（与分子同口径）⇒ 剔睡眠后这个比值会明显上升，
    #    那是正确结果：旧版的 36.5% 被 12.2h 睡眠（全归「维持」）压低了。
    # ⚠️ v3.60.36 起「体验」独立成格 ⇒ 本比值**不再包含旅游时长**。
    toward_ratio = round(hours['成长'] / covered, 4) if covered else 0.0

    # 六类小时**先定格到两位小数**，之后一律以它为准（见下方 `covered_hours`）
    hours_out = {k: round(v, 2) for k, v in hours.items()}
    covered_hours = round(sum(hours_out.values()), 2)
    # 「已记录」与「已剔睡眠」在屏幕上是相邻的两个数，用户真的会相加 ——
    # 剔除量按「全部记录 − 已记录（显示值）」回算，保证两者相加 == 全部记录。
    # 直接对原始值取整会差 0.0x，读起来像「有一块时间没交代」。
    excluded_hours = round(max(covered + excluded - covered_hours, 0.0), 2)

    return {
        'hours': hours_out,
        # 🔴 报出去的总数 = **上面那六个格子（已四舍五入）的和**，不是原始和。
        #    屏幕上这六个数是会被加起来的（用户真的会加）；如果总数按原始值取整，
        #    两者会差 0.0x（实测 33.96 显示成「六类加起来 34.00」），
        #    读起来像「有一类没算进去」——而这正是本函数上一版真正的病。
        #    身份改成「报出来的数之间自洽」：Σ(显示值) == 显示总数，永远成立。
        # ⚠️ `toward_ratio` / `fallback` 仍按原始值算：它们是**比值/分项**，
        #    不该被显示精度污染（否则「成长占比」会随四舍五入抖动）。
        'covered_hours': covered_hours,
        # 被剔除的睡眠小时（夜间 + 午睡）：只是**报出来**，不进六类、不进分子。
        # ⚠️ 它和 `covered_hours` 相加 == 区间内全部记录时长（含睡眠的原始和）。
        'excluded_sleep_hours': excluded_hours,
        # 兜底归因的小时：>0 说明有任务名没在映射表里设默认归因（不是错，但要看得到）
        'fallback_hours': round(fallback, 2),
        'theoretical_hours': round(theoretical, 2),
        # 分母的「每天几小时」也下发：页面要写「按每天 14h 可支配估算」，
        # 前端若自己写死一个数，改口径时必然忘一处（v3.64.25）。
        'theoretical_daily_hours': THEORETICAL_DAILY_HOURS,
        'coverage_rate': coverage_rate,
        'coverage_warn': coverage_rate < COVERAGE_WARN_THRESHOLD,
        'toward_ratio': toward_ratio,
        'days_elapsed': days_elapsed,
    }


def compute_unit_cost(start, end, net_self):
    """单位赎回成本 = 为自己净消耗 / 净赎回小时（elapsed_days × 8h）。

    ⚠️ `net_self`（= `self_expense − self_income`）由调用方传入，本函数不自己再算一遍：
       它通常刚在 `compute_pool_balance` 里算过，重算就是同一个窗口两次查库。
    ⚠️ 返回 `None` = 区间还一天都没走到（分母为 0），不是「成本为 0」。
    """
    today = min(date.today(), end)
    elapsed_days = max((today - start).days + 1, 0)
    redeemed_hours = elapsed_days * REDEEMED_DAILY_HOURS
    if redeemed_hours <= 0:
        return None
    return round(net_self / redeemed_hours, 2)
