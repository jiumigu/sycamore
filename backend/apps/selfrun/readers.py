"""自我运转 · 取数器（8 个 reader）+ 周期区间 + 配置指纹

🔴 三条判据（照抄设计稿 §8 / §2.4）：

1. **不做任意查询构建器** —— 任意查询 = 口径可以静默配错、且没有测试能钉住它。
   这里只实现**注册表里那 8 个**；`source_config.kind` 不命中就直接报错，**不静默跳过**。
2. **取不到返回 `None` + `issues`，绝不返回 0** ——
   `0` 是「源里确实一条都没有」（真 0），`None` 是「取不到」（系统不知道）。
   两者界面表现相反：前者显示「0h」，后者显示「—」+ 原因。
3. **半开区间** `[start, end)` —— `date` 列与 `datetime` 列混用时，闭区间会把边界日重复计入。
"""
import datetime as dt
import hashlib
import json

from django.db.models import Sum, Count, Min, Max
from django.utils import timezone

from apps.temporal.models import TemporalTask, TaskMeta, OneDayPage
from apps.health.models import HealthRecord
from apps.wealth.models import WealthBillList, WealthBalanceList, WealthAssetSnapshot

from .constants import READER_KEYS, MODULE_VALUE_WHITELIST


# ══════════════════════════════════════════════════════════════
# 周期区间（一律半开）
# ══════════════════════════════════════════════════════════════

def week_range(ref: dt.date):
    """ISO 周：`[周一, 下周一)`。返回 `(start, end, key)`，key = `2026-W42`。"""
    mon = ref - dt.timedelta(days=ref.weekday())
    iso = mon.isocalendar()
    return mon, mon + dt.timedelta(days=7), f'{iso[0]}-W{iso[1]:02d}'


def month_range(ref: dt.date):
    """自然月：`[月初, 下月初)`。返回 `(start, end, key)`，key = `2026-10`。"""
    first = ref.replace(day=1)
    nxt = (first + dt.timedelta(days=32)).replace(day=1)
    return first, nxt, f'{first:%Y-%m}'


def period_range(period_type: str, ref: dt.date):
    """按周期类型分派。返回 `(start, end, key)`。"""
    if period_type == 'weekly':
        return week_range(ref)
    if period_type == 'monthly':
        return month_range(ref)
    raise ValueError(f'未知周期类型：{period_type!r}')


def _aware(day: dt.date, end_of_day: bool = False) -> dt.datetime:
    """把 date 变成**带时区**的 datetime（`USE_TZ=True` 下必须，否则刷 RuntimeWarning）。"""
    t = dt.time.max if end_of_day else dt.time.min
    return timezone.make_aware(dt.datetime.combine(day, t))


def _empty(value=None, count=0, breakdown=None, warnings=None, **extra):
    """统一的 reader 返回结构。`value` 允许为 `None`（= 取不到）。"""
    out = {
        'value': value,
        'count': count,
        'breakdown': breakdown or [],
        'warnings': warnings or [],
        'freshness_at': None,      # 数据源最近一条的时间（service 层判 stale 用）
    }
    out.update(extra)
    return out


# ══════════════════════════════════════════════════════════════
# ① temporal_hours —— 按 L1/L2/L3 过滤 → 时长求和 / 有记录天数
# ══════════════════════════════════════════════════════════════

def _temporal_filtered(where: dict, start: dt.date, end: dt.date):
    """返回 (queryset, meta 字典)。

    🔴 维度映射以**库里的 `temporal_task_meta`** 为准（不是常量表）：
       L1 = `default_attribution`、L2 = `activity_type`、L3 = `task_name`。
       常量表只是「出生证」，库里那行才是真源。
    🔴 `growth=True` 是**另一根轴**：读 `counts_growth`（成长计时的唯一依据），
       不再看 L2 —— 用户 2026-11-01 拍板「开关说了算」，改分类不许暗改成长口径。
    """
    meta = {m.task_name: m for m in TaskMeta.objects.all()}
    names = set(meta.keys())

    l1 = set(where.get('l1') or [])
    l2 = set(where.get('l2') or [])
    l3 = set(where.get('l3') or [])
    if l1 or l2:
        names = {
            n for n in names
            if (not l1 or meta[n].default_attribution in l1)
            and (not l2 or meta[n].activity_type in l2)
        }
    growth = where.get('growth')
    if growth is not None:
        want = bool(growth)
        names = {n for n in names if bool(meta[n].counts_growth) is want}
    if l3:
        # `l3` 就是 task_name 白名单，与 l1/l2 取**并集**（设计稿要求：并集不是交集）
        names |= l3

    qs = TemporalTask.objects.filter(
        start_time__gte=_aware(start), start_time__lt=_aware(end),
    )
    # `end_time` 是为「这一周我做了什么」的时段轴取的（v3.64.35）：那张图要知道
    # 每件事从几点到几点，只有 `duration_hours` 摆不出位置。
    # 放 `.only()` 里而不是让调用方二次查库 —— 否则一条记录一次查询，一周几十次。
    rows = [r for r in qs.only('task_name', 'duration_hours', 'start_time', 'end_time')
            if r.task_name in names]
    return rows, meta


def temporal_rows(where: dict, start: dt.date, end: dt.date):
    """公开入口：按 `where`（l1/l2/l3）过滤出的原始时间行。

    给**非 KPI 场景**复用（例如每周复盘里的「流失统计」）——
    那些地方不需要 `run_reader` 的一整套 value/breakdown/freshness 结构，
    但必须和 KPI **用同一套维度映射与半开区间**（`_temporal_filtered`）。
    """
    rows, _meta = _temporal_filtered(where or {}, start, end)
    return rows


def _hours_rollup(where: dict, start: dt.date, end: dt.date):
    """时长合计 + 按 `task_name`（= L3）分行 —— `temporal_hours` / `growth_hours` 的唯一实现。

    🔴 两个取数器只差「筛选条件从哪来」，**取数与分行那段不许各写一份**：
       曾经同一件事写两遍，改了一处忘了另一处，两个数就悄悄不一样了。
    """
    rows, meta = _temporal_filtered(where, start, end)
    per = {}
    days = set()
    for r in rows:
        h = float(r.duration_hours or 0)
        item = per.setdefault(r.task_name, {'value': 0.0, 'count': 0})
        item['value'] += h
        item['count'] += 1
        if r.start_time:
            days.add(r.start_time.date())
    breakdown = [
        {
            'label': k,
            'value': round(v['value'], 2),
            'count': v['count'],
            'l2': meta[k].activity_type if k in meta else None,
        }
        for k, v in sorted(per.items(), key=lambda x: -x[1]['value'])
    ]
    fresh = TemporalTask.objects.aggregate(m=Max('start_time'))['m']
    return _empty(
        value=round(sum(v['value'] for v in per.values()), 2),
        count=len(rows),
        breakdown=breakdown,
        freshness_at=fresh,
        day_count=len(days),
    )


def temporal_hours(metric, start: dt.date, end: dt.date):
    """时长求和（小时）。`where` 由 KPI 配置给（l1 / l2 / l3）。"""
    cfg = metric.source_config or {}
    return _hours_rollup(cfg.get('where') or {}, start, end)


def growth_hours(metric, start: dt.date, end: dt.date):
    """成长计时（小时）：映射编辑器里勾了「成长计时」的任务名，时长合计。

    🔴 口径**固定**、不读 `metric.source_config.where` —— 成长计时只有一根轴
       （`task_meta.counts_growth`）。留一个可配的 where 就等于允许两处定义同一个量，
       而「改 L2 顺便改了成长口径」正是这次要消灭的那种隐式规则。
    ⚠️ `metric` 参数保留只为与其它取数器同签名（注册表统一调用）。
    """
    return _hours_rollup({'growth': True}, start, end)


def temporal_days(metric, start: dt.date, end: dt.date):
    """**有记录的天数**（社交连接用：聊过一次就算一天）。"""
    cfg = metric.source_config or {}
    rows, meta = _temporal_filtered(cfg.get('where') or {}, start, end)
    per = {}
    for r in rows:
        if not r.start_time:
            continue
        d = r.start_time.date()
        item = per.setdefault(d, {'value': 0.0, 'count': 0})
        item['value'] += float(r.duration_hours or 0)
        item['count'] += 1
    breakdown = [
        {'label': str(d), 'value': round(v['value'], 2), 'count': v['count'], 'l2': None}
        for d, v in sorted(per.items())
    ]
    fresh = TemporalTask.objects.aggregate(m=Max('start_time'))['m']
    return _empty(
        value=float(len(per)),
        count=len(rows),
        breakdown=breakdown,
        freshness_at=fresh,
    )


# ══════════════════════════════════════════════════════════════
# ② diary_migu_count —— 日记流输出（条数 / 字数）
# ══════════════════════════════════════════════════════════════

def diary_migu_count(metric, start: dt.date, end: dt.date):
    """`OneDayPage.otype='MIGU'` 的条数。

    🔴 **只能精确等 `'MIGU'`**，不能用排除法 —— `otype` 有 64 行越界值
    （生活记录 28 / 生活感悟 13 / 生活观察 6 / 书读后感 5 / 工作记录 4 /
     人生观察 3 / 怪异梦境 3 / 观影记录 2），
    写成「非 ONEDAY」之类会把这 64 行算成输出。
    """
    cfg = metric.source_config or {}
    where = cfg.get('where') or {}
    exact = where.get('otype_eq', 'MIGU')
    qs = OneDayPage.objects.filter(begin_date__gte=start, begin_date__lt=end)
    rows = list(qs.filter(otype=exact))
    words = sum(int(r.page or 0) for r in rows)
    breakdown = [
        {'label': str(r.begin_date), 'value': 1, 'count': 1, 'l2': None,
         'extra': {'title': r.title, 'words': int(r.page or 0)}}
        for r in sorted(rows, key=lambda x: x.begin_date)
    ]
    warnings = []
    # 顺手报「越界值」——不报的话没人会知道有 64 行不属于任何枚举
    out_of_choices = (
        OneDayPage.objects.filter(begin_date__gte=start, begin_date__lt=end)
        .exclude(otype__in=OTYPE_CHOICES_SET)
        .count()
    )
    if out_of_choices:
        warnings.append({
            'code': 'otype_out_of_choices',
            'count': out_of_choices,
            'hint': '本期日记流有记录类型不在枚举内，未计入',
        })
    fresh = OneDayPage.objects.aggregate(m=Max('begin_date'))['m']
    return _empty(
        value=float(len(rows)), count=len(rows), breakdown=breakdown,
        warnings=warnings, freshness_at=fresh, word_count=words,
    )


# 越界值判定用：把 OneDayPage 自己的 OTYPE_CHOICES 取出来
OTYPE_CHOICES_SET = {c[0] for c in OneDayPage.OTYPE_CHOICES}


# ══════════════════════════════════════════════════════════════
# ③ step_days —— 有步数的天数（出门）
# ══════════════════════════════════════════════════════════════

def step_days(metric, start: dt.date, end: dt.date):
    """`health_step_info` 里有步数记录的天数。

    ⚠️ 该源**已 30 天没更新**（`MAX(time)`）⇒ 一上线就是 `stale`。
       这不是「没做」，是「没记」—— 界面必须说清（V1）。
    """
    qs = HealthRecord.objects.filter(
        time__gte=_aware(start), time__lt=_aware(end),
    ).exclude(steps__isnull=True).exclude(steps=0)
    per = {}
    for r in qs.only('time', 'steps'):
        if not r.time:
            continue
        d = r.time.date()
        item = per.setdefault(d, {'steps': 0, 'count': 0})
        item['steps'] += int(r.steps or 0)
        item['count'] += 1
    breakdown = [
        {'label': str(d), 'value': v['steps'], 'count': v['count'], 'l2': None}
        for d, v in sorted(per.items())
    ]
    fresh = HealthRecord.objects.aggregate(m=Max('time'))['m']
    return _empty(
        value=float(len(per)), count=len(per), breakdown=breakdown, freshness_at=fresh,
    )


# ══════════════════════════════════════════════════════════════
# ④ bill_income —— 收入验证
# ══════════════════════════════════════════════════════════════

def bill_income(metric, start: dt.date, end: dt.date):
    """账单明细侧的收入求和（**可逐笔溯源**）。

    🔴 **两把尺子打架，此处显式选账单侧**：
       月结表 `wealth_balance_list.otherincome` 自 2026-05 起就是 0.0（停更），
       账单侧还在记（2026-07 有 1447 元、2026-10 有 6000 元）。
       ⇒ 取数走账单明细，并**在 `warnings` 里报月结表那边的差异**（V2：让你看见尺子）。
    """
    cfg = metric.source_config or {}
    where = cfg.get('where') or {}
    qs = WealthBillList.objects.filter(
        date__gte=_aware(start), date__lt=_aware(end),
        transaction_type=where.get('transaction_type', '收入'),
    )
    if where.get('category'):
        qs = qs.filter(category=where['category'])
    rows = list(qs)
    total = round(sum(float(r.amount or 0) for r in rows), 2)
    breakdown = [
        {
            'label': str(r.date.date()),
            'value': float(r.amount or 0),
            'count': 1,
            # 🔴 溯源行显示**子分类**，不是分类：分类是账本的大桶
            #    （「其他收入」这种，信息量接近零），子分类才说得清钱从哪来
            #    （「经营所得」/「意外来钱」）。没有子分类的老记录才回落到分类 ——
            #    宁可粗一点，也不要空一格。
            'l2': r.subcategory or r.category,
            'extra': {
                # 键名是 `note`（前端 `ReadingCard` 读的就是这个）——
                # 从前写成 `notes`，于是备注（如「公众号」）在界面上**一直没显示**。
                'note': r.notes or '',
                'category': r.category or '',
                'subcategory': r.subcategory or '',
            },
        }
        for r in sorted(rows, key=lambda x: x.date)
    ]

    warnings = []
    # 月结表侧对比：同一件事的第二个数，不一致必须说出来
    ym = f'{start:%Y-%m}'
    bal = WealthBalanceList.objects.filter(yearmon=ym).first()
    other = float(bal.otherincome or 0) if bal else None
    if other is not None and other != total:
        warnings.append({
            'code': 'income_two_rulers',
            'monthly_table': other,
            'bill_table': total,
            'hint': f'月结表 {ym} 的「其他收入」填的是 {other}，账单侧有 {len(rows)} 笔合计 {total}',
        })
    if bal is None:
        warnings.append({
            'code': 'no_monthly_row',
            'hint': f'月结表还没有 {ym} 这一行 —— 本月还没做月度复盘',
        })

    # 🔴 **新鲜度必须由「取数那张表」给出** —— 这里取的是账单明细，
    #    就不能拿月结表 `MAX(yearmon)` 去判它过没过期。
    #    反例（2026-10-18 现场）：月结表最新一期是 2026-09（47 天）⇒ 判 `stale`
    #    ⇒ `verdict='unknown'`、本期不计入判定；而账单侧 2026-10-15 才记过（3 天），
    #    本期明明已经取到 6,012.64 元。**两处各自都对，合起来是错的。**
    #    ⚠️ 月结表那边的滞后仍然要说 —— 但由下面 `no_monthly_row` /
    #       `income_two_rulers` 两条 warning 承担，那是「两把尺子」的事，
    #       不是「这条 KPI 取不到」的理由。
    fresh = WealthBillList.objects.aggregate(m=Max('date'))['m']
    return _empty(
        value=total, count=len(rows), breakdown=breakdown,
        # ⚠️ 这里**不能再套 `_yearmon_to_date`**：那是给 `'2026-09'` 这种字符串用的，
        #    喂一个 datetime 进去会被拆成 `date(年, 月, 1)` —— 看着有值，
        #    实际把「10-15」说成「10-01」（同一类静默失败：值合理、语义错）。
        warnings=warnings, freshness_at=fresh,
    )


def _yearmon_to_date(yearmon):
    """`'2026-09'` → `date(2026, 9, 1)`（只用于算新鲜度天数）。"""
    if not yearmon:
        return None
    try:
        y, m = str(yearmon).split('-')[:2]
        return dt.date(int(y), int(m), 1)
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════════════════════
# ⑤ module_value —— 白名单单值
# ══════════════════════════════════════════════════════════════

def module_value(metric, start: dt.date, end: dt.date):
    """白名单里的「跨模块单值」。

    ⚠️ **键名必须完全命中白名单**（不做前缀匹配）。写错直接报错 ——
       「取不到就静默不渲染」会让键名写错看不出来（项目高频硬坑 ⑧）。
    """
    cfg = metric.source_config or {}
    key = (cfg.get('where') or {}).get('key')
    if key not in MODULE_VALUE_WHITELIST:
        raise ValueError(
            f'`module_value` 的键 {key!r} 不在白名单内（允许：{MODULE_VALUE_WHITELIST}）'
        )

    if key == 'wealth.snapshot_fresh':
        # 本月的 KPI 口径是「盘过几次」，`value=1` 是次数、**不是金额** ——
        # 溯源行的 `value` 之和必须 = 自动取到的值，否则「溯源」二字就不成立。
        # ⇒ 这一期**盘成了什么样**（科目数 / 总资产 / 负债 / 净资产）放进
        #    `extra.facts`，与次数并列，互不挤占（v3.62.34）。
        #
        # 🔴 汇总**复用 `rollup_items`**，不在这里再算一遍 —— 界面上同一期
        #    会出现两个「净资产」（资产盘点的汇总行 / 这里的溯源行），
        #    两把尺子必然在某个边界上分叉（自用资产、`include_in_balance_sheet`、
        #    停用科目……），而分叉是静默的。
        from apps.wealth.services.asset_service import rollup_items  # 延迟 import

        rows = list(WealthAssetSnapshot.objects.filter(
            snapshot_date__gte=start, snapshot_date__lt=end,
        ).prefetch_related('items__account'))
        breakdown = []
        for r in sorted(rows, key=lambda x: (x.snapshot_date or dt.date.min, x.id)):
            items = [(float(it.amount or 0), it.account) for it in r.items.all()]
            roll = rollup_items(items, borrow=float(r.borrow or 0))
            facts = [
                {'label': '科目', 'value': roll['counted_count'], 'kind': 'count'},
                {'label': '总资产', 'value': roll['total_assets'], 'kind': 'amount'},
                {'label': '负债', 'value': roll['borrow'], 'kind': 'amount'},
                {'label': '净资产', 'value': roll['net_worth'], 'kind': 'amount'},
            ]
            # 有「不计表」的科目（自用资产）时才多一项 —— 免得净资产看着少了
            # 一块钱却不知道为什么（那正是 §107 判据要防的「它去哪了」）。
            if roll['excluded_total']:
                facts.append(
                    {'label': '未计表', 'value': roll['excluded_total'], 'kind': 'amount'}
                )
            breakdown.append({
                'label': str(r.snapshot_date) if r.snapshot_date else r.yearmon,
                'value': 1, 'count': 1,
                # `l2` 放年月：盘点日与所属期不是一回事（10-03 盘的是 09 月），
                # 只显示日期的话，用户没法判断这是哪一期。
                'l2': r.yearmon,
                'extra': {
                    # 🔴 键名必须是 `note`（前端 `ReadingCard` 读的就是它）。
                    #    从前写成 `remarks` —— 与 `bill_income` 的 `notes`→`note`
                    #    同一类错：**两边都看着合理，所以从不报错，只是永远不显示**。
                    'note': r.remarks or '',
                    'facts': facts,
                },
            })
        fresh = WealthAssetSnapshot.objects.aggregate(m=Max('snapshot_date'))['m']
        return _empty(
            value=1.0 if rows else 0.0, count=len(rows), breakdown=breakdown,
            freshness_at=fresh,
        )

    # redemption.runway：现金池余额 ÷ 近 30 日日均净支出 ÷ 30 = **可支撑月数**
    # 🔴 2026-11-02 起真算。此前这里写死 `value=None`，理由是「月结表『结余』
    #    自 2026-06 起没填」—— 但赎回池的余额并不依赖那张表：它由
    #    本金 + 注入 − 为自己净支出 直接算得出，速度由账单流水滚动 30 天给。
    #    ⇒ 一个「算不出来的白名单项」挂了大半年，而它其实一直算得出来。
    # 🔴 v3.64.20 起数据源从 `redemption_period` 换成**长阶段**：赎回期已是本模块
    #    下的一个阶段，本金在 `ledger_config['pool_principal']`，窗口就是阶段起止。
    #    白名单键名**保留** `redemption.runway`（它已经写进用户配好的 KPI 定义里，
    #    改键名会让存量 KPI 静默失效 —— 那正是本模块最怕的长相）。
    from apps.redemption import services as rs
    from .services import get_open_long_stage

    # 🔴 只读路径不许 `get_or_create`（铁律：GET 不写库）⇒ 取「正在跑的那个长阶段」，
    #    没有就老实说「还没设」，不要顺手建一行。
    stage = get_open_long_stage()
    latest_bill = WealthBillList.objects.aggregate(d=Max('date'))['d']
    fresh = _aware(latest_bill.date()) if latest_bill else None
    if stage is None:
        return _empty(
            value=None, count=0,
            issues=[{'code': 'no_long_stage', 'hint': '还没有进行中的长阶段（阶段账本想算余额，得先有一个带本金的长阶段）'}],
            freshness_at=fresh,
        )

    principal = float((stage.ledger_config or {}).get('pool_principal') or 0)
    end = stage.end_date or timezone.localdate()
    injected, inject_ids = pool_inject_totals(stage.start_date, end)
    pool = rs.compute_pool_balance(
        principal, stage.start_date, end, injected, exclude_bill_ids=inject_ids,
    )
    avg_daily = rs.compute_avg_daily_self_net(stage.start_date, end)
    if avg_daily < 0:
        # 🔴 `0` 与负数不是一件事（v3.64.26）：净流入时不存在「撑到哪个月」，
        #    更不叫「没有为自己 的账」—— 同一屏的档位分布里可能明明有十几笔。
        return _empty(
            value=None, count=0,
            issues=[{
                'code': 'net_inflow',
                'hint': '近 30 天是净流入（进来的比花的多），不存在「撑多久」这回事',
            }],
            freshness_at=fresh,
        )
    if avg_daily == 0:
        # 🔴 `None` 而不是 0：没有速度可外推 ≠「只能再撑 0 个月」，两者结论相反
        return _empty(
            value=None, count=0,
            issues=[{
                'code': 'no_self_expense',
                'hint': '窗口内还没有「为自己」的账，日均净支出为 0，撑多久外推不出来',
            }],
            freshness_at=fresh,
        )

    months = round(pool['balance'] / avg_daily / 30, 2)
    return _empty(
        value=months,
        # 派生标量没有「源记录」，用 1 表示「一条读数」——
        # ⚠️ 不能用 0：`evaluate_verdict` 会把「count=0 且值=0」判成 `empty`（真的一条都没有），
        #    而余额刚好归零是另一个结论。
        count=1,
        breakdown=[{
            'label': '现金池 ÷ 日均净支出 ÷ 30',
            'value': months, 'count': 1, 'l2': None,
            'extra': {'note': '', 'facts': [
                {'label': '现金池余额', 'value': pool['balance'], 'kind': 'amount'},
                {'label': '日均净支出', 'value': avg_daily, 'kind': 'amount'},
            ]},
        }],
        freshness_at=fresh,
    )


# ══════════════════════════════════════════════════════════════
# ⑥ manual_sum —— 手工登记求和
# ══════════════════════════════════════════════════════════════

def manual_sum(metric, start: dt.date, end: dt.date):
    """区间内 `[start, end)` 的 `Checkin.value` 求和。

    ⚠️ **负数 = 冲销**（撤销不改不删）⇒ 直接求和即可，不过滤负数。
    """
    qs = metric.checkins.filter(checkin_date__gte=start, checkin_date__lt=end)
    rows = list(qs)
    total = round(sum(float(r.value or 0) for r in rows), 2)
    breakdown = [
        {
            'label': str(r.checkin_date), 'value': float(r.value or 0),
            'count': 1, 'l2': None, 'extra': {'note': r.note or '', 'id': r.id},
        }
        for r in sorted(rows, key=lambda x: (x.checkin_date, x.id))
    ]
    return _empty(value=total, count=len(rows), breakdown=breakdown)


# ══════════════════════════════════════════════════════════════
# ⑦ works_count —— 作品库（「留下件数」）
# ══════════════════════════════════════════════════════════════

def works_count(metric, start: dt.date, end: dt.date):
    """区间内**成形**的作品件数（按 `Work.created_at`，半开区间）。

    🔴 v3.62.0 口径变更：这条取代了「数日记流 MIGU 条数」（`diary_migu_count`）。
       理由与边界见 `templates.py` 的 `output_count` 那条注释。

    🔴 **作品表刻意不落 `period_key`** —— 期是「按创建时间现算」的纯派生值
       （ISO 周跨年也稳定），落库就是第二份真源，还会与现算值漂移。
       ⇒ 这里现算，且 `period_range` 是全项目**唯一**那把尺子。

    ⚠️ 返回 `0` 而不是 `None` —— 「这周一件都没留」是**事实**（真 0），
       不是「取不到」。这与 `module_value` 的 `redemption.runway` 相反：
       那边是「算不出来」，必须 `None` + `issues`。

    ⚠️ 延迟 import：`works` 的序列化器反向依赖本模块的 `period_range`，
       模块级 import 会让「先加载谁」变得要紧（能跑，但脆）。
    """
    from apps.works.constants import WORK_KIND_CHOICES
    from apps.works.models import Work

    qs = Work.objects.filter(
        created_at__gte=_aware(start), created_at__lt=_aware(end),
    )

    # 🔴 `where.work_kind`：按作品**类型**过滤（v3.64.30，为「这月画了几张」）。
    #    配错 / 写错类型名**必须抛错**，不能静默返 0 ——「0 件」是「真的没画」
    #    这个**事实**，而一个拼错的值换来的 0 会冒充同一条结论，页面上看不出来。
    where = ((metric.source_config if metric else None) or {}).get('where') or {}
    kind_filter = where.get('work_kind')
    if kind_filter:
        allowed = [v for v, _ in WORK_KIND_CHOICES]
        if kind_filter not in allowed:
            raise ValueError(f'未知的作品类型 {kind_filter!r}（允许：{allowed}）')
        qs = qs.filter(kind=kind_filter)

    rows = list(qs)
    breakdown = [
        {
            'label': r.name, 'value': 1, 'count': 1, 'l2': r.get_kind_display(),
            'extra': {
                'id': r.id,
                'status': r.get_status_display(),
                'summary': r.summary or '',
                'channel': r.channel or '',
                # 🔴 「成形于」要精确到**时刻**，不能只给日期：阶段账本的明细弹窗
                #    得让用户自己看出「11-05 21:40 合成」是不是落在阶段区间里
                #    （区间是半开的，边界那天的最后一小时算不算进来，光看日期无法自证）。
                # ⚠️ 必须 `localtime()`：从库里读出来的是 **UTC**，直接 `isoformat()`
                #    会发 `...T13:40:00+00:00`，前端截前 16 位就成了
                #    「差 8 小时、但看着完全合理」的错时间（最难发现的一种）。
                'created_at': timezone.localtime(r.created_at).isoformat(),
            },
        }
        for r in sorted(rows, key=lambda x: x.created_at)
    ]
    return _empty(value=float(len(rows)), count=len(rows), breakdown=breakdown)


# ══════════════════════════════════════════════════════════════
# 注册表 + 分派
# ══════════════════════════════════════════════════════════════

READERS = {
    'temporal_hours': temporal_hours,
    'growth_hours': growth_hours,
    'temporal_days': temporal_days,
    'diary_migu_count': diary_migu_count,
    'step_days': step_days,
    'bill_income': bill_income,
    'module_value': module_value,
    'manual_sum': manual_sum,
    'works_count': works_count,
}

# 断言注册表与常量真源一致（漏一个就早点炸，别等线上）
assert set(READERS) == set(READER_KEYS), '取数器注册表与 constants.READER_KEYS 不一致'


def run_reader(metric, start: dt.date, end: dt.date):
    """按 `metric.source_config.kind` 分派。

    🔴 未知 kind **直接抛错**，不静默跳过 ——
       「静默跳过」等于「静默改口径」，而它算出来的数**落在合理区间、不刺眼**。
    """
    kind = (metric.source_config or {}).get('kind')
    if kind not in READERS:
        raise ValueError(f'未知的取数器 {kind!r}（允许：{sorted(READERS)}）')
    return READERS[kind](metric, start, end)


# ══════════════════════════════════════════════════════════════
# 配置指纹（T4 的「尺子断门」）
# ══════════════════════════════════════════════════════════════

def canonical_json(obj) -> str:
    """稳定序列化 —— 键排序 + 无多余空格，保证同一份配置哈希一致。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def config_fingerprint(stage, resolved=None) -> str:
    """`sha256(...)[:16]` —— 「当时的尺子」。

    算入：`id` / `agg` / `source_kind` / `source_config` / `direction` / `goal_value` / `floor_value`
    不算入：`name` / `sort_order`（**改名不算换尺子**）
    ⚠️ 算入 `stage.id` ⇒ 复制出来的新阶段**指纹必然不同**（这是刻意的）。

    🔴 `resolved` = `{metric_id: (goal, floor)}`，**该期生效**的目标值。
       按期修订过目标（`SelfRunMetricPlan`）的阶段必须把它传进来 ——
       否则 W43 用 12h、W44 用 8h 会被算成**同一把尺子**，
       T4 的「尺子断点」分组就会把两段不可直接比的时期并成一段（**静默**）。
    """
    parts = [f'stage:{stage.id}']
    metrics = stage.metrics.filter(status='active').order_by('id')
    for m in metrics:
        goal, floor = m.goal_value, m.floor_value
        if resolved and m.id in resolved:
            goal, floor = resolved[m.id]
        parts.append('|'.join([
            f'metric:{m.id}',
            m.agg or '',
            m.source_kind or '',
            canonical_json(m.source_config or {}),
            m.direction or '',
            '' if goal is None else str(goal),
            '' if floor is None else str(floor),
        ]))
    raw = '\n'.join(parts)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def fingerprint_of_metrics(stage_id, metrics) -> str:
    """同上，但接受**尚未落库**的 metric 对象列表（T1 试算用，不写库）。"""
    parts = [f'stage:{stage_id}']
    for m in sorted(metrics, key=lambda x: (x.get('sort_order', 0), x.get('name', ''))):
        parts.append('|'.join([
            'metric:new',
            m.get('agg') or '',
            m.get('source_kind') or '',
            canonical_json(m.get('source_config') or {}),
            m.get('direction') or '',
            '' if m.get('goal_value') is None else str(m.get('goal_value')),
            '' if m.get('floor_value') is None else str(m.get('floor_value')),
        ]))
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════
# 池注入（v3.64.26：标记账单，不自记金额）
# ══════════════════════════════════════════════════════════════
def pool_inject_totals(start, end):
    """区间内**被标为「中途注入」的收入**合计，及这些账单的 id。

    🔴 金额一律**从账单读**，不读标记表 —— 标记表只存 `bill_id`。
       若另存一份金额，账单改了金额而标记没改，两个数就分叉，且两边各自都合理。
    🔴 只认 `transaction_type='收入'`：注入是钱进来。支出被标了也当没标
       （端点层会直接拒掉，这里再兜一层，免得脏数据把余额算歪）。
    🔴 返回的 id 列表给 `compute_pool_balance(exclude_bill_ids=...)` 用：
       被标注入的收入若同时是「为自己」，它已经会减少净消耗；这里必须把它排除，
       否则同一笔钱**加进注入又减消耗**，余额凭空多出一倍。
    ⚠️ 窗口口径与 `redemption.services._window_bounds` 一致（半开区间），
       直接复用那个函数，不在这里再写一遍日期边界。
    """
    from apps.redemption import services as rs
    from .models import SelfRunPoolInject

    bill_ids = list(SelfRunPoolInject.objects.values_list('bill_id', flat=True))
    if not bill_ids:
        return 0.0, []
    start_dt, end_dt = rs._window_bounds(start, end)
    rows = WealthBillList.objects.filter(
        id__in=bill_ids, transaction_type='收入',
        date__gte=start_dt, date__lt=end_dt,
    ).values_list('id', 'amount')
    total = 0.0
    kept = []
    for bill_id, amount in rows:
        kept.append(bill_id)
        total += float(amount or 0)
    return round(total, 2), kept
