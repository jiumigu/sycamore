"""比率体系 — 六项财务规划比率（v3.58.23，P2-A）

为什么要有这个模块
    报告 3.4 判定「比率分析 4/10」：已实现的四个指标（负债率/活期占比/
    公积金占比/月度储蓄率）阈值硬编码，且缺的六个恰是规划期最常引用的。
    本模块补齐其中**尚未具备**的五项（应急金月数已由 P0 落地在资产健康
    指标卡里，此处复算同一个数以保证两个展示位永不打架）：
        应急金月数 · 刚性支出覆盖率 · 被动收入覆盖率 · 债务收入比 DTI
        · 净值增长率 · 支出质量指数

四条口径纪律（违反即回归）
    ① **前端不做除法，也不持有任何阈值**。判定区间本身随接口下发
       （`constants.RATIO_BANDS` → `ratio_grade` → 响应里的 `bands`），
       前端只按 `level` 上色、按 `bands` 画刻度。
    ② **分子分母一起返回**。任何指标都能被追问「这个数怎么来的」，
       答案不该是「再算一遍」，而是响应里现成的两个数。
    ③ **不可用必须说清原因与补救动作，不返回 0**。
       0 与「没数据」在财务上完全不同：0% 的被动收入覆盖率是一个**结论**
       （完全靠主动收入），而「负债明细没录」根本不构成结论。
       用 0 冒充会让「没录入数据」显示出满分健康度 —— 正是报告点名
       要避免的「阈值与结论脱钩」。
    ④ **提示文案里不许嵌入金额**。金额要经前端 `formatAmount` 走脱敏，
       后端拼进字符串就等于绕过掩码（见 MEMORY 隐私口径 v3.58.18）。
       故 `hint` 只写定性话术，数字一律放在 `numerator` / `denominator` / `extra`。

数据源选择（关键取舍）
    `wealth_cash_flow`（旧，一行 8 列）与 `wealth_asset_snapshot`（新，
    按科目）**二选一，整条序列一起切**，不做逐月混合：
      · 新体系有任何一期快照 → 整体用新体系（旧期会显示为缺口，可用
        `wealth_seed_asset_accounts --with-snapshots` 回填）；
      · 否则整体用旧表。
    为什么不逐月「有新的用新的、没新的用旧的」：那会让一条趋势线在中间
    悄悄换过口径，**两期之间的净值增长可能有一半来自数据源切换**，
    而图上完全看不出来。宁可断一段（看得见），不要一条换过源的线（看不见）。

资产位置的两套语义（容易混，故写死）
    · `carry_forward=True`（总览用）：取**锚定月及其之前最近的一期**快照。
      语义是「到这个月为止我的资产是多少」——本月还没盘点时用上一期，
      与资产健康指标卡（取最新一期）永远一致。
    · `carry_forward=False`（按期查看用）：**必须精确命中该月**，
      没有就报「该月没有快照」。语义是「2026-06 那期盘点」。

已知限制（明说，不掩盖）
    · DTI 的分子是「当前每月应还」，属**时点存量属性**，历史月份没有对应
      数据 —— 故 DTI 不进趋势序列（见 RATIO_TREND_EXCLUDED）。
    · 净值增长率的净储蓄窗口按两次盘点的**日期**界定（半开区间，
      含期末日、不含期初日）。盘点日缺失时回落自然月并显式标注
      `bound='month'` —— 两种边界口径不同，不能混着说。
    · 支出质量指数依赖 `wealth_bill_list.necessity`（既有列，非本系统录入）。
      实测近 3 个月填写率 74%、全表仅 2.3%，故设了填写率门槛：
      样本不足时判「数据不足」，而不是拿 2% 的样本除以全量支出。
"""

from datetime import date, datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone

from apps.wealth.constants import (
    CLASSIFY_COUNTED_TYPES,
    EMERGENCY_EXPENSE_MONTHS,
    LEGACY_ASSET_ACCOUNTS,
    NECESSITY_IMPULSE,
    QUALITY_MIN_COVERAGE,
    RATIO_EXPENSE_MONTHS,
    RATIO_INCOME_MONTHS,
    RATIO_ORDER,
    RATIO_PASSIVE_MONTHS,
    RATIO_SOURCE_LABELS,
    RATIO_SOURCE_LEGACY,
    RATIO_SOURCE_SNAPSHOT,
    RATIO_TREND_EXCLUDED,
)
from apps.wealth.models import (
    WealthAssetSnapshot,
    WealthAssetSnapshotItem,
    WealthBillList,
    WealthLiabilityDetail,
)

from . import cashflow_service as cf_svc
from .expense_estimate import estimate_from_buckets
from .asset_service import rollup_items
from .classify_service import monthly_classified_totals
from .debt_service import ACTIVE_LIABILITY
from .ratio_grade import grade_ratio, ratio_meta


def _round(value, digits: int = 2):
    return None if value is None else round(float(value), digits)


def _ym_label(ym_key) -> str:
    key = int(ym_key or 0)
    return f'{key // 100:04d}-{key % 100:02d}'


def _span_label(ym_keys) -> str:
    keys = sorted(k for k in ym_keys if k)
    if not keys:
        return ''
    return f'{_ym_label(keys[0])} ~ {_ym_label(keys[-1])}'


def _prev_months(anchor_key: int, months: int) -> list[int]:
    """以 anchor_key 结尾、往前共 months 个自然月的键（**降序**，含 anchor）。"""
    year, month = int(anchor_key) // 100, int(anchor_key) % 100
    keys: list[int] = []
    for _ in range(max(int(months), 1)):
        keys.append(year * 100 + month)
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return keys


def _month_gap(start_key: int, end_key: int) -> int:
    """两个年月键之间相隔的月份数（end − start）。"""
    return ((int(end_key) // 100 * 12 + int(end_key) % 100)
            - (int(start_key) // 100 * 12 + int(start_key) % 100))


# ══════════════════════════════════════════════════════════════
# 资产位置：新科目快照优先，回落旧表，并声明来源
# ══════════════════════════════════════════════════════════════


def resolve_asset_source(user_id: int = 1) -> str | None:
    """整条序列用哪一套资产数据 —— 有任一新体系快照即整体切到新体系。

    返回值是 RATIO_SOURCE_* 之一，或 None（两套都没有数据）。
    """
    if WealthAssetSnapshot.objects.filter(user_id=user_id).exists():
        return RATIO_SOURCE_SNAPSHOT
    if cf_svc.get_snapshot_series():
        return RATIO_SOURCE_LEGACY
    return None


def _code_totals(rows: list[tuple[float, object]]) -> dict[str, float]:
    """[(金额, 科目)] → {科目 code: 金额}。

    同一 code 出现多行时**求和**而不是覆盖 —— 覆盖会让第二行静默顶掉第一行，
    是「少算了一笔却看不出」的典型形态。
    """
    out: dict[str, float] = {}
    for amount, account in rows:
        code = getattr(account, 'code', None)
        if not code:
            continue
        out[code] = _round(out.get(code, 0.0) + float(amount or 0))
    return out


def _snapshot_position(snap: WealthAssetSnapshot) -> dict:
    """新体系：明细行 → roll-up（**复用 asset_service.rollup_items**，不另算一份）。"""
    rows = [
        (item.amount, item.account)
        for item in WealthAssetSnapshotItem.objects
        .filter(snapshot=snap)
        .select_related('account')
    ]
    roll = rollup_items(rows, snap.borrow)
    return {
        'available': True,
        'source': RATIO_SOURCE_SNAPSHOT,
        'id': snap.id,
        'ym_key': int(str(snap.yearmon).replace('-', '')[:6] or 0),
        'yearmon': snap.yearmon,
        'snapshot_date': snap.snapshot_date,
        'remarks': snap.remarks or '',
        # 应急金分子 = 参与汇总且 is_liquid 的科目合计
        'liquid': roll['liquid_total'],
        # 应收 = 应收类科目合计，用于与快照头的 lend 对账
        'receivable': roll['category_totals'].get('应收', 0.0),
        'financial_assets': roll['financial_assets'],
        'self_use_total': roll['self_use_total'],
        'total_assets': roll['total_assets'],
        'available_net_worth': roll['available_net_worth'],
        'borrow': roll['borrow'],
        'net_worth': roll['net_worth'],
        # 按科目 code 的金额明细 —— 资产全景的饼图与固定列靠它渲染。
        # 旧表路径返回**同一形状**，消费方（cashflow_service）才不必为两个
        # 来源各写一套取值分支（2026-09-29 合并录入链路时补）。
        'accounts': _code_totals(rows),
    }


def _legacy_position(cf) -> dict:
    """旧表：一行 8 列 → 与 cashflow_service 完全相同的口径（勿另立一套）。"""
    liquid = cf_svc.sum_liquid_accounts(cf)
    provident_fund = float(cf.accumulationfund or 0)
    borrow = float(cf.borrow or 0)
    lend = float(cf.lend or 0)
    financial_assets = liquid + provident_fund
    total_assets = financial_assets + lend
    return {
        'available': True,
        'source': RATIO_SOURCE_LEGACY,
        'id': cf.baid,
        'ym_key': int(cf_svc.norm_yearmon(cf.yearmon).replace('-', '') or 0),
        'yearmon': cf_svc.norm_yearmon(cf.yearmon),
        'snapshot_date': cf.btime,
        'remarks': cf.remarks or '',
        'liquid': _round(liquid),
        'receivable': _round(lend),
        # 旧表没有自用资产概念 —— 显式给 0 而不是省略字段，
        # 否则前端得为两个来源各写一套取值分支。
        'self_use_total': 0.0,
        'financial_assets': _round(financial_assets),
        'total_assets': _round(total_assets),
        'available_net_worth': _round(financial_assets - borrow),
        'borrow': _round(borrow),
        'net_worth': _round(total_assets - borrow),
        # 与 _snapshot_position 同形状：8 个账户列 + 借出款
        'accounts': {
            code: _round(getattr(cf, code, None) or 0)
            for code, *_rest in LEGACY_ASSET_ACCOUNTS
        },
    }


def resolve_asset_series(user_id: int = 1) -> dict[int, dict]:
    """{ym_key: 资产位置} —— 来源整条一致（见模块 docstring 的取舍说明）。"""
    source = resolve_asset_source(user_id)
    series: dict[int, dict] = {}
    if source == RATIO_SOURCE_SNAPSHOT:
        for snap in WealthAssetSnapshot.objects.filter(user_id=user_id).order_by('yearmon'):
            pos = _snapshot_position(snap)
            if pos['ym_key']:
                series[pos['ym_key']] = pos
    elif source == RATIO_SOURCE_LEGACY:
        for cf in cf_svc.get_snapshot_series():
            pos = _legacy_position(cf)
            if pos['ym_key']:
                series[pos['ym_key']] = pos
    return series


def resolve_asset_position(yearmon: str | None = None, user_id: int = 1,
                           carry_forward: bool = False) -> dict:
    """取资产位置。

    yearmon 为空 → 最新一期。
    carry_forward=True → 取该月**及其之前最近**的一期（总览语义：
        「到这个月为止我有多少资产」；本月未盘点时用上一期，与健康指标卡一致）。
    carry_forward=False → 必须精确命中该月（按期查看语义）。

    取不到时返回 `{'available': False, 'reason': ...}` —— 调用方据此把
    依赖资产的比率整批判为「数据不足」，而不是当成 0。
    """
    source = resolve_asset_source(user_id)
    if source is None:
        return {
            'available': False, 'source': None, 'yearmon': None, 'ym_key': None,
            'snapshot_date': None, 'carried': False,
            'reason': '既没有旧表盘点记录，也没有新科目快照',
        }

    series = resolve_asset_series(user_id)
    if not series:
        return {
            'available': False, 'source': source, 'yearmon': None, 'ym_key': None,
            'snapshot_date': None, 'carried': False,
            'reason': '该来源下没有可用快照',
        }

    if not yearmon:
        pos = dict(series[max(series)])
        pos['carried'] = False
        return pos

    key = int(cf_svc.norm_yearmon(yearmon).replace('-', '')[:6] or 0)
    if carry_forward:
        candidates = sorted(k for k in series if k <= key)
        if not candidates:
            return {
                'available': False, 'source': source, 'yearmon': None, 'ym_key': None,
                'snapshot_date': None, 'carried': False,
                'reason': f'{_ym_label(key)} 之前没有资产快照',
            }
        picked = candidates[-1]
        pos = dict(series[picked])
        # carried=True 表示「这个数取自更早的一期」——必须让前端看得见，
        # 否则用户会以为本月已经盘点过。
        pos['carried'] = picked != key
        return pos

    pos = series.get(key)
    if pos is None:
        return {
            'available': False, 'source': source, 'yearmon': _ym_label(key),
            'ym_key': key, 'snapshot_date': None, 'carried': False,
            'reason': f'{_ym_label(key)} 没有资产快照',
        }
    out = dict(pos)
    out['carried'] = False
    return out


# ══════════════════════════════════════════════════════════════
# 净储蓄：两次盘点之间的收支净额
# ══════════════════════════════════════════════════════════════


def _net_saving(start_pos: dict, end_pos: dict, user_id: int = 1) -> dict:
    """期初 → 期末之间的净储蓄（收入 − 支出）。

    ⚠️ 只在两端的盘点日都存在且期初 < 期末时按**日**取半开区间
       `(期初日, 期末日]`：期初那天发生的一切已经体现在期初余额里，
       再算一次就是重复计。两端日期缺失/倒挂时回落自然月区间并标注
       `bound='month'` —— 两种边界口径不同，不可混说，故显式回报用了哪种。

    ⚠️ 只统计 收入 / 支出，**不含转入转出与余额变更**（与分类层同一条排除
       规则）。转入转出是账户间搬运，计进来会让净储蓄凭空多出一笔；
       实测转入转出成对出现且金额恒等（2026-04 各 21 笔 48310）。
    """
    start_day = start_pos.get('snapshot_date')
    end_day = end_pos.get('snapshot_date')
    start_key, end_key = start_pos.get('ym_key'), end_pos.get('ym_key')

    if isinstance(start_day, date) and isinstance(end_day, date) and start_day < end_day:
        start_dt = timezone.make_aware(
            datetime.combine(start_day + timedelta(days=1), time.min)
        )
        end_dt = timezone.make_aware(
            datetime.combine(end_day + timedelta(days=1), time.min)
        )
        agg = (
            WealthBillList.objects
            .filter(
                user_id=user_id,
                transaction_type__in=CLASSIFY_COUNTED_TYPES,
                date__gte=start_dt, date__lt=end_dt,
            )
            .order_by()
            .values('transaction_type')
            .annotate(total=Sum('amount'))
        )
        income = expense = 0.0
        for row in agg:
            if row['transaction_type'] == '收入':
                income += float(row['total'] or 0)
            else:
                expense += float(row['total'] or 0)
        return {
            'income': _round(income),
            'expense': _round(expense),
            'net_saving': _round(income - expense),
            'bound': 'snapshot_date',
            # 统一给字符串：这两个值进的是 `extra` 字典（DRF DictField 原样透传），
            # 混进 date 对象会让「日期」与「年月」两种颗粒度的值在前端难以分辨。
            'period_start': start_day.isoformat(),
            'period_end': end_day.isoformat(),
        }

    gap = _month_gap(start_key or 0, end_key or 0)
    keys = _prev_months(end_key, gap) if end_key and gap > 0 else []
    income = sum(cf_svc.monthly_flow_totals('收入', keys, user_id).values())
    expense = sum(cf_svc.monthly_flow_totals('支出', keys, user_id).values())
    return {
        'income': _round(income),
        'expense': _round(expense),
        'net_saving': _round(income - expense),
        'bound': 'month',
        'period_start': _ym_label(min(keys)) if keys else None,
        'period_end': _ym_label(end_key) if end_key else None,
    }


def _growth_level(residual) -> tuple:
    """净值增长率的级别由**残差符号**派生 —— 报告未给判定线，不发明阈值。

    残差的含义：净资产变化中**无法用储蓄解释**的部分。
      正 → 净资产涨得比存下的还多（投资收益，或漏记的收入）；
      负 → 净资产没跟上储蓄（亏损，或漏记的支出）。
    所以它只能读方向、不能读绝对值大小 —— 这就是不设区间的理由。
    """
    if residual is None:
        return None, None
    if residual > 0.01:
        return 'good', '高于储蓄'
    if residual < -0.01:
        return 'danger', '低于储蓄'
    return 'normal', '与储蓄一致'


# ══════════════════════════════════════════════════════════════
# 比率项构造
# ══════════════════════════════════════════════════════════════


def _leg(name: str, value) -> dict:
    return {'label': name, 'value': _round(value)}


def _ratio(key: str, value=None, *, numerator=None, denominator=None,
           hint: str = '', reason: str | None = None,
           level: str | None = None, level_label: str | None = None,
           extra: dict | None = None, available: bool | None = None) -> dict:
    """组装一个比率项 —— 六项比率**统一由本函数产出**，形状一致。

    `available` 不传时按 value 是否为 None 推断：有值即可用。
    """
    meta = ratio_meta(key)
    if level is None and level_label is None:
        graded = grade_ratio(key, value)
        level, level_label = graded['level'], graded['level_label']
    if available is None:
        available = value is not None
    return {
        'key': key,
        'label': meta['label'],
        'unit': meta['unit'],
        'direction': meta['direction'],
        'formula': meta['formula'],
        # 口径说明随每一项下发 —— 气泡提示直接渲染，前端不另写文案。
        'note': meta['note'],
        'value': _round(value),
        'bands': meta['bands'],
        'target': meta['target'],
        'level': level,
        'level_label': level_label,
        'numerator': numerator,
        'denominator': denominator,
        'available': available,
        'reason': reason,
        'hint': hint or '',
        'extra': extra or {},
    }


def _missing(key: str, reason: str, *, numerator=None, denominator=None,
             hint: str = '', extra: dict | None = None) -> dict:
    """不可用的比率 —— 一律带上原因，绝不返回 0 冒充结论。"""
    return _ratio(key, None, numerator=numerator, denominator=denominator,
                  reason=reason, hint=hint, extra=extra, available=False)


def _months_with_records(buckets: list, field: str) -> list:
    """筛出「有记录」的月份。

    口径：**该维度金额非零的月份才算有记录**。
    ⚠️ 不除以固定月数：把没记录的月份当成零支出，会把月均拉低、
       把「还能活几个月」抬高 —— 那是往乐观方向错，最不该犯的方向。
    """
    return [b for b in buckets if b and (b.get(field) or 0)]


def _active_liabilities(user_id: int = 1):
    """在还负债的查询集 —— DTI 与负债台账共用同一个「在还」定义。"""
    return WealthLiabilityDetail.objects.filter(
        user_id=user_id, status=ACTIVE_LIABILITY,
    ).order_by()


# ══════════════════════════════════════════════════════════════
# 六项比率的计算（总览与趋势共用同一实现）
# ══════════════════════════════════════════════════════════════


def _build_ratios(anchor_key: int, buckets: dict, asset_series: dict,
                  position: dict, debt_monthly=None, include_dti: bool = True,
                  user_id: int = 1) -> list:
    """在给定锚定月上算出六项比率。

    总览与趋势**共用本函数**：一份实现，两条出口。
    若分成两份，迟早出现「总览说 12.8 个月、趋势最后一点说 13.1」这种事 ——
    而两者本来指的是同一个数。

    ⚠️ `position` 由调用方解析后传入（总览用 carry_forward 语义）：
       不在这里按 anchor_key 直接查表，否则「本月未盘点」会让整组资产类
       比率集体变成「无数据」，而健康指标卡同时还在显示上一期的数字。
    """

    def win(months: int) -> list:
        return [buckets[k] for k in _prev_months(anchor_key, months) if k in buckets]

    liquid = position.get('liquid')
    asset_ym = position.get('yearmon')
    asset_extra = {'asset_yearmon': asset_ym, 'asset_carried': position.get('carried', False)}
    ratios: list = []

    # ① 应急金月数 ────────────────────────────────────────────
    # 🔴 分母的**计算**不在这里 —— 单一实现在 `expense_estimate` 模块，
    #    健康指标卡调的是同一个函数。此处曾自己算「近 3 个月算术平均」，
    #    而卡片走的是另一条 SQL（未剔除转账），于是同一个「应急金月数」
    #    在两张卡上可以差出好几个月。现在统一为 12 个月三点估算。
    #    ⚠️ `expense_window` / `expense_months` 下面 ②⑥ 还要用，别跟着删。
    #    趋势要为每个点各算一次分母，故这里用 `estimate_from_buckets`
    #    复用**已经取好的** buckets —— 自己去查库就是 N+1。
    expense_window = win(RATIO_EXPENSE_MONTHS)
    expense_months = _months_with_records(expense_window, 'expense_total')
    estimate = estimate_from_buckets(buckets, anchor_key)
    expense_avg = estimate.get('value')
    if liquid is None:
        ratios.append(_missing(
            'emergency_months', '没有可用的资产快照',
            hint='先补一期资产盘点，才能把现金折算成「能活几个月」',
        ))
    elif expense_avg is None:
        ratios.append(_missing(
            'emergency_months',
            estimate.get('reason') or '窗口内没有支出记录，无法折算月数',
            numerator=_leg('现金类资产', liquid), extra=asset_extra,
            hint='没有支出记录时月数无从谈起，先记几笔支出',
        ))
    else:
        ratios.append(_ratio(
            'emergency_months', liquid / expense_avg,
            numerator=_leg('现金类资产', liquid),
            denominator=_leg(f'近 {EMERGENCY_EXPENSE_MONTHS} 月支出三点估算', expense_avg),
            hint='按当前支出水平能撑住的月数；分母是中位数加权的三点估算，'
                 '单笔大额不会把基准带飞',
            extra={**asset_extra,
                   'record_months': estimate.get('months_with_records'),
                   'window_label': _span_label(
                       d['ym_key'] for d in (estimate.get('detail') or [])),
                   'pert_optimistic': estimate.get('optimistic'),
                   'pert_likely': estimate.get('likely'),
                   'pert_pessimistic': estimate.get('pessimistic')},
        ))

    # ② 刚性支出覆盖率 ────────────────────────────────────────
    rigid_monthly = (
        sum(b['expense_nature'].get('固定', 0.0) for b in expense_months)
        / len(expense_months) if expense_months else None
    )
    # ⚠️ 「刚性占支出」的分母是本项**自己窗口内**的平均支出，不是应急金的
    #    三点估算值 —— 后者是 12 个月 PERT，拿它做比值等于把「刚性占比」
    #    这个比例的分母悄悄换成了另一把尺子（分子 3 个月、分母 12 个月）。
    expense_window_avg = (
        sum(b['expense_total'] for b in expense_months) / len(expense_months)
        if expense_months else None
    )
    if liquid is None:
        ratios.append(_missing(
            'rigid_coverage', '没有可用的资产快照',
            hint='先补一期资产盘点',
        ))
    elif not rigid_monthly:
        ratios.append(_missing(
            'rigid_coverage', '刚性支出未归类或为 0，无法计算覆盖月数',
            numerator=_leg('现金类资产', liquid), extra=asset_extra,
            hint='刚性支出靠分类规则里的「固定」标签得出，先在分类规则台账补规则',
        ))
    else:
        ratios.append(_ratio(
            'rigid_coverage', liquid / rigid_monthly,
            numerator=_leg('现金类资产', liquid),
            denominator=_leg('月刚性支出', rigid_monthly),
            hint='断收后只靠现金能覆盖固定开销的月数，比应急金月数更接近底线',
            extra={**asset_extra,
                   'rigid_share': _round(rigid_monthly / expense_window_avg * 100, 1)
                   if expense_window_avg else None},
        ))

    # ③ 被动收入覆盖率 ────────────────────────────────────────
    passive_window = win(RATIO_PASSIVE_MONTHS)
    passive_income = sum(b['income_type'].get('被动', 0.0) for b in passive_window)
    passive_expense = sum(b['expense_total'] for b in passive_window)
    if passive_expense <= 0:
        ratios.append(_missing(
            'passive_coverage', f'近 {RATIO_PASSIVE_MONTHS} 个月没有支出记录',
            numerator=_leg('被动收入', passive_income),
            hint='覆盖率的分子要靠支出规模才有意义',
        ))
    else:
        ratios.append(_ratio(
            'passive_coverage', passive_income / passive_expense * 100,
            numerator=_leg(f'近 {RATIO_PASSIVE_MONTHS} 月被动收入', passive_income),
            denominator=_leg(f'近 {RATIO_PASSIVE_MONTHS} 月总支出', passive_expense),
            hint='财务自由度的定义式：被动收入覆盖多少开销',
            extra={'window_label': _span_label(b['ym_key'] for b in passive_window)},
        ))

    # ④ 债务收入比 DTI ────────────────────────────────────────
    if include_dti:
        income_window = win(RATIO_INCOME_MONTHS)
        income_months = _months_with_records(income_window, 'income_total')
        income_avg = (
            sum(b['income_total'] for b in income_months) / len(income_months)
            if income_months else None
        )
        if debt_monthly is None:
            ratios.append(_missing(
                'dti', '没有「在还」状态的负债明细，「每月应还」无从取得',
                hint='在「负债明细台账」录一笔在还债务（含每月应还），DTI 才有分子；'
                     '账单里没有还款类流水，无法从流水反推',
            ))
        elif not income_avg:
            ratios.append(_missing(
                'dti', f'近 {RATIO_INCOME_MONTHS} 个月没有收入记录',
                numerator=_leg('月债务还款', debt_monthly),
                hint='收入是 DTI 的分母，没有收入记录时算不出比例',
            ))
        else:
            ratios.append(_ratio(
                'dti', debt_monthly / income_avg * 100,
                numerator=_leg('月债务还款', debt_monthly),
                denominator=_leg(f'近 {RATIO_INCOME_MONTHS} 月月均收入', income_avg),
                hint='月供吃掉多少收入；负债侧唯一有意义的过程指标',
                extra={'record_months': len(income_months),
                       'window_label': _span_label(b['ym_key'] for b in income_months)},
            ))

    # ⑤ 净值增长率 ────────────────────────────────────────────
    pos_key = position.get('ym_key')
    earlier = sorted(k for k in asset_series if pos_key and k < pos_key)
    prev_asset = asset_series[earlier[-1]] if earlier else None
    end_net = position.get('net_worth')
    if not position.get('available') or pos_key not in asset_series:
        ratios.append(_missing(
            'net_worth_growth',
            f'{_ym_label(anchor_key)} 没有本期的资产快照（资产数取自更早一期，'
            f'不足以支撑增长口径）',
            hint='净值增长率必须用同一期的两端对照，不能拿上一期的余额充数',
        ))
    elif prev_asset is None:
        ratios.append(_missing(
            'net_worth_growth', '没有更早一期资产快照可作期初',
            hint='至少两期盘点才能谈增长',
        ))
    elif not prev_asset.get('net_worth') or prev_asset['net_worth'] <= 0:
        ratios.append(_missing(
            'net_worth_growth', '期初净资产不为正，增长率无意义',
            numerator=_leg('期末净资产', end_net),
            denominator=_leg('期初净资产', prev_asset.get('net_worth')),
            hint='期初净资产为负时任何「增长率」都会给出误导性的符号',
        ))
    else:
        prev_net = prev_asset['net_worth']
        saving = _net_saving(prev_asset, position, user_id)
        delta = (end_net or 0) - prev_net
        residual = delta - saving['net_saving']
        level, label = _growth_level(residual)
        ratios.append(_ratio(
            'net_worth_growth', residual / prev_net * 100,
            numerator=_leg('净资产变化', delta),
            denominator=_leg('期初净资产', prev_net),
            level=level, level_label=label,
            hint='残差 = 净资产变化里用储蓄解释不了的部分：为正说明涨得比存的多'
                 '（投资收益或漏记收入），为负说明没跟上储蓄（亏损或漏记支出）',
            extra={
                'prev_yearmon': prev_asset.get('yearmon'),
                'net_saving': saving['net_saving'],
                'saving_income': saving['income'],
                'saving_expense': saving['expense'],
                'residual': _round(residual),
                'bound': saving['bound'],
                'period_start': saving['period_start'],
                'period_end': saving['period_end'],
            },
        ))

    # ⑥ 支出质量指数 ──────────────────────────────────────────
    quality_rows = sum(b['necessity']['total_rows'] for b in expense_window)
    quality_filled = sum(b['necessity']['filled_rows'] for b in expense_window)
    coverage = (quality_filled / quality_rows) if quality_rows else 0.0
    impulse = sum(
        b['necessity']['amounts'].get(NECESSITY_IMPULSE, 0.0)
        for b in expense_window
    )
    expense_3m = sum(b['expense_total'] for b in expense_window)
    if not quality_rows:
        ratios.append(_missing(
            'expense_quality', '窗口内没有支出记录',
            hint='该指标需要逐笔标注「必要 / 可选 / 冲动」',
        ))
    elif coverage < QUALITY_MIN_COVERAGE:
        ratios.append(_missing(
            'expense_quality',
            f'支出行的「必要 / 可选 / 冲动」填写率仅 {round(coverage * 100, 1)}%，'
            f'低于 {int(QUALITY_MIN_COVERAGE * 100)}% 门槛',
            hint='样本不足时算出来的比例不是结论，先补标注再回来看',
            extra={'coverage': round(coverage, 4), 'filled_rows': quality_filled,
                   'total_rows': quality_rows},
        ))
    elif expense_3m <= 0:
        ratios.append(_missing(
            'expense_quality', '窗口内支出合计为 0',
            extra={'coverage': round(coverage, 4)},
        ))
    else:
        ratios.append(_ratio(
            'expense_quality', impulse / expense_3m * 100,
            numerator=_leg('冲动消费', impulse),
            denominator=_leg(f'近 {RATIO_EXPENSE_MONTHS} 月总支出', expense_3m),
            hint='报告口径是「趋势下降为改善」，不设绝对判定线；看这条线有没有往下走',
            extra={'coverage': round(coverage, 4), 'filled_rows': quality_filled,
                   'total_rows': quality_rows,
                   'window_label': _span_label(b['ym_key'] for b in expense_window)},
        ))

    # 统一按 RATIO_ORDER 排序 —— 保证总览与趋势的序列顺序一致，
    # 前端可以直接按下标对齐两条出口的数据。
    order = {key: idx for idx, key in enumerate(RATIO_ORDER)}
    ratios.sort(key=lambda r: order.get(r['key'], 99))
    return ratios


# ══════════════════════════════════════════════════════════════
# 对外入口
# ══════════════════════════════════════════════════════════════


def _debt_monthly_payment(user_id: int = 1):
    """在还债务的每月应还合计。

    ⚠️ **没有任何在还债务行时返回 None，而不是 0**：
       0 是「没有债」（DTI = 0，健康），None 是「没录负债明细」（不可知）。
       用 0 冒充会让一个没录入数据的系统显示出满分健康度。
       台账有行但都不在「在还」时同样返回 None，但原因不同 ——
       由 `get_ratio_overview` 用 `_liability_state` 分辨后写进 reason。
    """
    rows = _active_liabilities(user_id).values_list('monthly_payment', flat=True)
    values = [float(v or 0) for v in rows]
    if not values:
        return None
    return sum(values)


def _liability_state(user_id: int = 1) -> dict:
    """负债台账的可用状态 —— 用于把 DTI 的「为什么不可用」说准。"""
    total = WealthLiabilityDetail.objects.filter(user_id=user_id).count()
    active = _active_liabilities(user_id).count()
    if not total:
        return {'total': 0, 'active': 0, 'state': 'empty'}
    if not active:
        return {'total': total, 'active': 0, 'state': 'none_active'}
    return {'total': total, 'active': active, 'state': 'ok'}


def get_ratio_overview(anchor_yearmon: str | None = None, user_id: int = 1) -> dict:
    """比率总览 —— 六项比率的当前值、判定、分子分母与取数窗口。

    锚定月为空时锚定「当前自然月」（与资产健康指标卡的应急金口径一致），
    以便本接口给出的应急金月数与卡片上的数字**永远相同**。
    """
    now = datetime.now()
    anchor_key = (
        int(cf_svc.norm_yearmon(anchor_yearmon).replace('-', '')[:6])
        if anchor_yearmon else now.year * 100 + now.month
    )

    source = resolve_asset_source(user_id)
    asset_series = resolve_asset_series(user_id)
    # 总览用 carry_forward：「到这个月为止我的资产是多少」
    position = resolve_asset_position(anchor_yearmon, user_id, carry_forward=True)

    # 一次取够最长窗口（被动收入 12 个月）的按月归类结果，
    # 其余窗口都从这里切片 —— 少打 5 次库，也保证各窗口同源。
    buckets = monthly_classified_totals(
        cf_svc.recent_ym_keys(RATIO_PASSIVE_MONTHS, anchor_yearmon), user_id
    )

    ratios = _build_ratios(
        anchor_key, buckets, asset_series, position,
        debt_monthly=_debt_monthly_payment(user_id), include_dti=True,
        user_id=user_id,
    )

    # DTI 的不可用原因按台账状态说准 —— 「完全没录」与「录了但都不在还」
    # 需要用户做不同的事，一句「数据不足」等于没说。
    liability_state = _liability_state(user_id)
    if liability_state['state'] == 'none_active':
        for ratio in ratios:
            if ratio['key'] == 'dti' and not ratio['available']:
                ratio['reason'] = (
                    f'负债台账有 {liability_state["total"]} 笔，但没有一笔是「在还」状态'
                )
                ratio['hint'] = '把仍在偿还的债务状态改为「在还」，或补录在还债务'

    gaps = [
        {'key': r['key'], 'label': r['label'], 'reason': r['reason'], 'hint': r['hint']}
        for r in ratios if not r['available']
    ]

    return {
        'anchor_yearmon': _ym_label(anchor_key),
        'asset_source': source,
        'asset_source_label': RATIO_SOURCE_LABELS.get(source or '', '无数据'),
        # 无论可取与否都给出同一形状 —— 不可取时 available=False + reason，
        # 前端不必为「有/无资产数据」写两套取值分支。
        'asset_position': position,
        'liability_state': liability_state,
        'windows': {
            'expense': {
                'months': RATIO_EXPENSE_MONTHS,
                'label': _span_label(cf_svc.recent_ym_keys(RATIO_EXPENSE_MONTHS, anchor_yearmon)),
            },
            'income': {
                'months': RATIO_INCOME_MONTHS,
                'label': _span_label(cf_svc.recent_ym_keys(RATIO_INCOME_MONTHS, anchor_yearmon)),
            },
            'passive': {
                'months': RATIO_PASSIVE_MONTHS,
                'label': _span_label(cf_svc.recent_ym_keys(RATIO_PASSIVE_MONTHS, anchor_yearmon)),
            },
        },
        'ratios': ratios,
        'gaps': gaps,
    }


def get_ratio_trend(months: int = 12, user_id: int = 1) -> dict:
    """比率趋势 —— 逐月的比率值序列（**值已在后端算好，前端不做除法**）。

    ⚠️ 为给最早那个月凑出滚动窗口（应急金 / 被动收入都要往前 12 个月），
       实际取数范围比展示范围更宽：展示 N 个月、另多取最宽窗口的月数。
       否则最早的几个点窗口是残缺的，值与总览算出来的对不上。
    ⚠️ 资产位置**不做 carry_forward**：趋势里某一期没有盘点就该是缺口，
       拿上一期余额去重复填点会画出一条不存在的平线。
    ⚠️ DTI 不入序列：分子是「当前每月应还」，是时点存量属性，
       拿今天的月供去算历史 12 个月是**伪造历史**。
    """
    months = max(int(months or 12), 1)
    display_keys = sorted(cf_svc.recent_ym_keys(months))     # 升序

    # 多取「最宽窗口」几个月，让展示区最早一个点也有完整滚动窗口。
    # ⚠️ 用 EMERGENCY_EXPENSE_MONTHS 而不是 RATIO_PASSIVE_MONTHS：两者月数
    #    都是 12，但**锚定方式差一格** —— 被动收入窗口含锚定月，应急金窗口
    #    取的是「锚定月之前的 12 个完整月」（不含锚定月）。按被动收入的宽度
    #    取数，最早那个点会永远差一个月、少一个样本，值与总览对不上。
    fetch_keys = cf_svc.recent_ym_keys(months + EMERGENCY_EXPENSE_MONTHS)
    buckets = monthly_classified_totals(fetch_keys, user_id)
    asset_series = resolve_asset_series(user_id)

    series: dict = {}
    for ym_key in display_keys:
        ratios = _build_ratios(
            ym_key, buckets, asset_series, asset_series.get(ym_key) or {},
            debt_monthly=None, include_dti=False, user_id=user_id,
        )
        for ratio in ratios:
            # setdefault 而不是预置全部键：被排除的比率（DTI）**不该**在 series
            # 里留一个空数组 —— 前端拿到 `dti: []` 会以为「这个月没有数据」，
            # 而真相是「这个指标永远不进趋势」。排除的事由 `excluded` 说明。
            series.setdefault(ratio['key'], []).append({
                'ym': _ym_label(ym_key),
                'value': ratio['value'],
                'level': ratio['level'],
                'level_label': ratio['level_label'],
                'available': ratio['available'],
            })

    return {
        'months': [_ym_label(k) for k in display_keys],
        'asset_source': resolve_asset_source(user_id),
        'series': series,
        'excluded': [
            {'key': key, 'label': ratio_meta(key)['label'], 'reason': reason}
            for key, reason in RATIO_TREND_EXCLUDED.items()
        ],
    }


def available_anchor_months(user_id: int = 1, limit: int = 24) -> list:
    """可作为锚定月的年月列表（倒序）—— 由资产快照的期别决定。

    比率总览的锚定月本质是「看哪一期」，故候选来自**快照期别**，
    而不是账单期别（账单可能比盘点更密，选了没有快照的月份只会得到空白）。
    """
    keys = sorted(resolve_asset_series(user_id), reverse=True)
    return [_ym_label(k) for k in keys[:limit]]
