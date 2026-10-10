"""现金盘点服务 — 资产全景、趋势、健康指标、对账

口径（v3.58.19 财务规划口径纠偏，常量见 apps/wealth/constants.py）：
    金融资产 = 活期账户 + 公积金            → summary.total（数值不变，仅前端标签归位）
    总资产   = 金融资产 + 应收借出          → summary.total_assets
    净资产   = 总资产 − 负债                → summary.net_worth
比率类指标（负债率/活期占比/公积金占比）统一以**总资产**为分母，三者可比；
应急金以「月数」判定，不再用绝对金额；判定级别由 `ratio_grade` 查
`constants.RATIO_BANDS` 得出 —— **前端不再自己算阈值**（v3.58.23 收回）。

⚠️ 旧表 wealth_cash_flow 允许**同一 yearmon 存在多行**（同一个月盘点了不止一次；
   实测 2025-05 / 2025-08 / 2025-09 / 2026-03 / 2026-06 各有两行）。
   因此本模块所有「按期取数」一律走 `get_snapshot_series()` 去重
   （同月取 btime 最新一行）：
     · 直接用 `.get(yearmon=...)` 会抛 MultipleObjectsReturned —— 这是**真实 500**，
       不是理论风险（2026-06 就有两行）；
     · 按 `-yearmon` 取前 N 条会把同一个月算成两个点 —— 趋势图同一 x 轴两个 y。
"""

from datetime import datetime

from django.db import connection

from apps.wealth.constants import (
    EMERGENCY_EXPENSE_MONTHS,
    EMERGENCY_MONTHS_TARGET,
    LIQUID_ACCOUNT_FIELDS,
    RATIO_INCOME_MONTHS,
)
from apps.wealth.models import WealthCashFlow

from .expense_estimate import get_monthly_expense_estimate
from .ratio_grade import grade_ratio


def norm_yearmon(value) -> str:
    """年月归一为 `YYYY-MM`。

    旧表存的是带横杠的 7 位串（实测全表统一），但 `copy_last_month` 历史上
    处理过不带横杠的写法，故这里做归一 —— 让「2026-6 / 2026-06 / 202606 / 20266」
    四种写法都命中同一期，而不是各自成为一期。
    ⚠️ 5 位数字（`2026-6` 去掉分隔符后是 5 位）必须补零成两位月份，
       否则 `2026-6` 与 `2026-06` 会被当成两期，同期多行的问题会以
       「换个写法就多出一期」的形式复现。
    """
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    if len(digits) == 6:
        return f'{digits[:4]}-{digits[4:]}'
    if len(digits) == 5:
        return f'{digits[:4]}-0{digits[4:]}'
    return str(value or '').strip()


def get_snapshot_series() -> list[WealthCashFlow]:
    """按 yearmon 去重后的快照序列，**年月升序**。

    同月多行取 `btime` 最新的那一行（并列时取 baid 最大）——
    「一期一条」这条约定由本函数独家保证，别在别处再写一遍去重。
    """
    rows = (
        WealthCashFlow.objects
        .filter(yearmon__isnull=False)
        .order_by('yearmon', 'btime', 'baid')
    )
    by_key: dict[str, WealthCashFlow] = {}
    for cf in rows:
        by_key[norm_yearmon(cf.yearmon)] = cf   # 后写覆盖前写 → 留最新
    return [by_key[k] for k in sorted(by_key)]


def get_snapshot_index() -> dict[str, WealthCashFlow]:
    """{`YYYY-MM`: 快照} —— 给按期的单点查询用，避免每次线性扫描。"""
    return {norm_yearmon(cf.yearmon): cf for cf in get_snapshot_series()}


def recent_ym_keys(months: int, anchor_yearmon: str | None = None) -> list[int]:
    """最近 N 个自然月的 `year*100+month` 键，**从锚定月往前**（含锚定月）。

    anchor_yearmon 为空时锚定「当前自然月」——这是「看现在」的语义。
    传了锚定月则用于历史回看与比率趋势（同一套窗口逻辑复用于任意月份，
    避免「趋势按今天算、总览按上月算」的口径分叉）。
    """
    if anchor_yearmon:
        norm = norm_yearmon(anchor_yearmon)
        try:
            year, month = int(norm[:4]), int(norm[5:7])
        except (TypeError, ValueError):
            year, month = datetime.now().year, datetime.now().month
    else:
        now = datetime.now()
        year, month = now.year, now.month

    keys: list[int] = []
    for _ in range(max(int(months), 1)):
        keys.append(year * 100 + month)
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return keys


def monthly_flow_totals(transaction_type: str, ym_keys: list[int],
                        user_id: int = 1) -> dict[int, float]:
    """按 (year, month) 汇总某收支类型的金额 → {ym_key: 金额}。

    ⚠️ 只返回**有记录**的月份 —— 调用方据此把「无记录的月份」排除出分母。
       若除以固定的 N，无记录月份会被当成零支出，把月均拉低、月数虚高。
    ⚠️ 用账单自带的 year / month 整型列过滤，不碰 date 字段 ——
       `wealth_bill_list.date` 是 datetime 且受 USE_TZ 影响，按日期推导须半开区间。
    """
    if not ym_keys:
        return {}
    placeholders = ','.join(['%s'] * len(ym_keys))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT `year`, `month`, COALESCE(SUM(amount), 0)
            FROM wealth_bill_list
            WHERE user_id = %s AND transaction_type = %s
              AND (`year` * 100 + `month`) IN ({placeholders})
            GROUP BY `year`, `month`
            """,
            [user_id, transaction_type, *ym_keys],
        )
        rows = cursor.fetchall()
    return {int(r[0]) * 100 + int(r[1]): float(r[2] or 0)
            for r in rows if r and r[0] and r[1]}


def sum_liquid_accounts(cf) -> float:
    """活期类账户合计 — 应急金分子。

    科目以 constants.LIQUID_ACCOUNT_FIELDS 为单一真源：
    含银行卡活期（T+0 可取而原实现漏计），不含公积金与定期存款。
    """
    return sum(float(getattr(cf, f, None) or 0) for f in LIQUID_ACCOUNT_FIELDS)


def get_recent_monthly_income(user_id: int = 1,
                              months: int = RATIO_INCOME_MONTHS,
                              anchor_yearmon: str | None = None) -> dict:
    """近 N 个自然月的平均月收入 — DTI 的分母。

    ⚠️ 支出侧（应急金分母）已改用三点估算，见 `expense_estimate` 模块；
       本函数只服务收入侧（DTI 的分母），**不要拿它去算月支出** ——
       它的取数路径没有剔除转入转出，与分类台账口径不一致。
    与支出侧同构（只对有记录的月份求均值），但**不给 balance_list 回落**：
    `wealth_balance_list` 的收支列口径与账单明细并不严格对齐，用它当分子
    会让 DTI 与其它比率来自两把不同的尺子。

    ⚠️ 返回值同时给出 `months_with_records` 与 `total`：收入是**脉冲式**的
       （按月发薪、偶尔一次性），只看均值看不出样本是否单薄。窗口内只有
       一笔年终奖时，均值会被抬高、DTI 被压低 —— 这个字段就是让人看得见
       这种情形，而不是把一个单点样本当成稳态收入。
    """
    ym_keys = recent_ym_keys(months, anchor_yearmon)
    totals = monthly_flow_totals('收入', ym_keys, user_id)
    count = len(totals)
    total = sum(totals.values())
    return {
        'monthly_avg': round(total / count, 2) if count else 0.0,
        'total': round(total, 2),
        'months_with_records': count,
        'window_months': int(months),
        'ym_keys': ym_keys,
    }


def _asset_position():
    """资产位置解析的桥。

    🔴 函数内导入而非模块级：`ratio_service` 在模块级
    `from . import cashflow_service`，若这里也在模块级反向导入就成环。
    解析的唯一实现在 ratio_service.resolve_asset_*（新体系优先、旧表回落），
    本模块只消费、不重写。
    """
    from . import ratio_service
    return ratio_service


def _r2(value) -> float:
    """转 float 并保留 2 位（缺值 → 0.0）。仅用于列表/趋势的展示字段。"""
    return round(float(value or 0), 2)


class _PositionRow:
    """把 asset_position 的位置视图适配成 `_build_overview` 认得的「类旧表行」。

    `_build_overview` 的入参是鸭子类型（`test_cashflow_metrics` 用
    SimpleNamespace 直接驱动口径测试），所以适配只发生在**切源这一层**，
    算式一行不改 —— 改算式等于同时改掉那批口径测试的语义。
    """

    def __init__(self, pos: dict):
        self._accounts = {
            str(k): float(v or 0) for k, v in (pos.get('accounts') or {}).items()
        }
        self.borrow = float(pos.get('borrow') or 0)
        self.btime = pos.get('snapshot_date')
        self.yearmon = pos.get('yearmon')
        self.remarks = pos.get('remarks') or ''

    def __getattr__(self, name: str):
        # 科目被停用/删掉时返回 0，而不是让 AttributeError 冒到接口层
        if name.startswith('_'):
            raise AttributeError(name)
        return self._accounts.get(name, 0.0)


def get_cashflow_overview(user_id: int = 1,
                          anchor_yearmon: str | None = None) -> dict | None:
    """获取指定期的资产全景（含按当前支出水平折算的应急金月数）

    anchor_yearmon 为空 = 取最新一期快照；传值则取该期（历史回看）。
    两条路径共用 `get_snapshot_series()` 的去重口径，故「最新一期」与
    「按期取」永远指同一条记录 —— 这是「月度最新」与「按月跳转」
    两个入口给出同一组数字的前提。

    🔴 应急金分母**锚定到快照自身那一期**（`picked.yearmon`），不是「今天」：
       分子是那一期的时点存量，分母就该是那一期之前的支出水平 ——
       两者时点不一致时，月数里会混进「快照是三个月前拍的」这种错位，
       而且快照越旧错得越多。窗口取该月**之前的 12 个完整月**
       （不含盘点当月，理由见 `expense_estimate` 模块头）。
    """
    pos = _asset_position().resolve_asset_position(anchor_yearmon, user_id)
    if not pos.get('available'):
        return None

    return _build_overview(
        _PositionRow(pos),
        get_monthly_expense_estimate(user_id, pos['yearmon']),
        anchor_yearmon=pos['yearmon'],
        metrics=pos,
    )


def get_cashflow_by_yearmon(yearmon: str) -> dict | None:
    """按年月获取资产快照（历史回看，不折算月数）

    与 `get_cashflow_overview` **同源**（都走 asset_position），所以「最新一期」
    与「按期跳转」对同一期永远给出同一组数字。
    """
    if not norm_yearmon(yearmon or ''):
        return None
    pos = _asset_position().resolve_asset_position(yearmon, carry_forward=False)
    if not pos.get('available'):
        return None
    return _build_overview(_PositionRow(pos), metrics=pos)


def _build_overview(cf: WealthCashFlow, expense_estimate: dict | None = None,
                    anchor_yearmon: str | None = None,
                    metrics: dict | None = None) -> dict:
    """构建资产全景响应

    expense_estimate: `expense_estimate.get_monthly_expense_estimate()` 的返回值
        （含三点估算的 O / M / P 与样本月数）。传 None、或 `value` 为 None，
        表示分母算不出来 —— 月数类指标一律置 None，**绝不回落成 0**：
        0 是「月支出为零」这个结论，与「没有数据」是两件事。
        真正的计算在 `expense_estimate` 模块，本函数只做除法。
    anchor_yearmon: 本期快照的期别，用于说明「月数按哪一期折算」。
    metrics: 可选。已由 `ratio_service.resolve_asset_*` 解析好的口径值
        （liquid / financial_assets / total_assets / net_worth / receivable）。
        **新体系的 financial_assets 含应收、total_assets 含自用资产**，与旧表
        8 列口径不同，不能在这里用旧公式重算 —— 所以给了 metrics 就直接采用。
        不给则按旧表 8 列口径现算（旧路径与 `test_cashflow_metrics` 的内存
        对象走这条），口径测试因此不受切源影响。
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

    borrow = float(cf.borrow or 0)
    accumulationfund = float(cf.accumulationfund or 0)

    if metrics:
        # 口径由 asset_position 给定：新体系下「金融资产」含应收借出、
        # 「总资产」含自用资产，与下面这条旧公式不等价，故不重算。
        flow_total = float(metrics.get('liquid') or 0)
        lend = float(metrics.get('receivable') or 0)
        financial_assets = float(metrics.get('financial_assets') or 0)
        total_assets = float(metrics.get('total_assets') or 0)
        net_worth = float(metrics.get('net_worth') or 0)
    else:
        flow_total = sum_liquid_accounts(cf)
        lend = float(cf.lend or 0)
        financial_assets = flow_total + accumulationfund   # wealth_cash_flow.total 的既有口径
        total_assets = financial_assets + lend             # 总资产：补回应收借出
        net_worth = total_assets - borrow                  # 净资产（数值等于原 realnum）

    # 应急金分母 = 近 EMERGENCY_EXPENSE_MONTHS 个月支出的三点估算（PERT）。
    # 分母的**计算**不在这里 —— 单一实现在 `expense_estimate` 模块，
    # 比率面板调的是同一个函数。本函数只负责相除与定级。
    estimate = expense_estimate or {}
    expense_value = estimate.get('value')
    monthly_expense = float(expense_value) if expense_value else 0.0

    # 应急金 = 活期类账户合计（含银行卡活期）；月数需月均支出方可折算
    emergency_fund = flow_total
    if monthly_expense > 0:
        emergency_months = round(emergency_fund / monthly_expense, 1)
        emergency_target_amount = round(monthly_expense * EMERGENCY_MONTHS_TARGET, 2)
        emergency_gap = round(max(emergency_target_amount - emergency_fund, 0), 2)
    else:
        emergency_months = None
        emergency_target_amount = None
        emergency_gap = None

    # 判定级别由后端给出（阈值真源 constants.RATIO_BANDS）——
    # 前端此前用 `months >= target / 2` 自己算警戒线，等于阈值仍由前端定义，
    # 改后端常量不会改变界面结论。progress_pct 也一并算好，
    # 让前端只做展示、不做除法。
    emergency_grade = grade_ratio('emergency_months', emergency_months)
    emergency_pct = (
        round(min(emergency_months / EMERGENCY_MONTHS_TARGET, 1.0) * 100, 1)
        if emergency_months is not None and EMERGENCY_MONTHS_TARGET else None
    )

    # 三个占比指标统一以「总资产」为分母，保证互相可比
    debt_ratio = round(borrow / total_assets * 100, 1) if total_assets > 0 else 0
    debt_ratio_legacy = round(borrow / financial_assets * 100, 1) if financial_assets > 0 else 0
    liquidity_ratio = round(flow_total / total_assets * 100, 1) if total_assets > 0 else 0
    pf_ratio = round(accumulationfund / total_assets * 100, 1) if total_assets > 0 else 0

    # 三个占比的判定级别同样收回后端 —— 卡上四项指标的档位从此**全部**由
    # constants.RATIO_BANDS 决定，前端一个阈值数字都不留。
    liquidity_grade = grade_ratio('liquidity_ratio', liquidity_ratio)
    debt_grade = grade_ratio('debt_ratio', debt_ratio)
    pf_grade = grade_ratio('provident_fund_ratio', pf_ratio)

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
            'emergency_months_level': emergency_grade['level'],
            'emergency_months_level_label': emergency_grade['level_label'],
            'emergency_months_pct': emergency_pct,
            'emergency_target_amount': emergency_target_amount,
            'emergency_gap': emergency_gap,
            # 分母的三点估算底稿一并下发：O / M / P 与样本月数。
            # 气泡提示要能说清「这个基准是怎么来的」，只给一个结果数是说不清的。
            'expense_estimate': estimate or None,
            'monthly_expense_window': int(EMERGENCY_EXPENSE_MONTHS),
            'expense_basis_yearmon': (estimate or {}).get('anchor_yearmon'),
            'liquidity_ratio': liquidity_ratio,
            'liquidity_ratio_level': liquidity_grade['level'],
            'liquidity_ratio_level_label': liquidity_grade['level_label'],
            'debt_ratio': debt_ratio,
            'debt_ratio_level': debt_grade['level'],
            'debt_ratio_level_label': debt_grade['level_label'],
            'debt_ratio_legacy': debt_ratio_legacy,
            'provident_fund_ratio': pf_ratio,
            'provident_fund_ratio_level': pf_grade['level'],
            'provident_fund_ratio_level_label': pf_grade['level_label'],
        },
    }


def get_asset_trend(user_id: int = 1, months: int = 12) -> list[dict]:
    """获取资产趋势数据（每月含流动性、金融资产、总资产、净资产）

    ⚠️ 必须走 `get_snapshot_series()`（按月去重）：直接 `order_by('-yearmon')[:N]`
       会把同月的两次盘点算成两个点 —— 趋势图上同一 x 轴出现两个 y，
       且「近 12 个月」实际只覆盖不到 12 个自然月。
    """
    series = _asset_position().resolve_asset_series(user_id)
    if not series:
        return []

    keys = sorted(series)
    if months:
        keys = keys[-int(months):]

    trend = []
    for k in keys:
        pos = series[k]
        act = pos.get('accounts') or {}
        trend.append({
            'yearmon': pos['yearmon'],
            'flow_total': _r2(pos.get('liquid')),
            'total': _r2(pos.get('financial_assets')),
            'financial_assets': _r2(pos.get('financial_assets')),
            'total_assets': _r2(pos.get('total_assets')),
            'net_worth': _r2(pos.get('net_worth')),
            'accumulationfund': _r2(act.get('accumulationfund')),
            'zplay': _r2(act.get('zplay')),
            'wechat': _r2(act.get('wechat')),
            'jianbank': _r2(act.get('jianbank')),
            'gongbank': _r2(act.get('gongbank')),
            'zhongbank': _r2(act.get('zhongbank')),
            'nongbank': _r2(act.get('nongbank')),
            'borrow': _r2(pos.get('borrow')),
            'lend': _r2(pos.get('receivable')),
        })
    return trend


def get_snapshot_list(page: int = 1, page_size: int = 12, user_id: int = 1) -> dict:
    """获取盘点历史列表（分页）

    数据源已切到 asset_position（2026-09-29 合并录入链路）—— 与顶部三块、
    六项比率取同一份数据、同一批期次。响应形状（items/total/page/page_size）
    **保持不变**，让仍挂在页面上的 `SnapshotHistory` 即便留着也不会崩。
    """
    series = _asset_position().resolve_asset_series(user_id)
    ordered = [series[k] for k in sorted(series, reverse=True)]   # 年月倒序

    total = len(ordered)
    offset = max(int(page) - 1, 0) * int(page_size)
    picked = ordered[offset:offset + int(page_size)]

    result_items = []
    for pos in picked:
        act = pos.get('accounts') or {}
        date_value = pos.get('snapshot_date')
        result_items.append({
            'baid': pos.get('id'),
            'yearmon': pos.get('yearmon'),
            'btime': str(date_value) if date_value else None,
            'flow_total': _r2(pos.get('liquid')),
            'total': _r2(pos.get('financial_assets')),
            'financial_assets': _r2(pos.get('financial_assets')),
            'total_assets': _r2(pos.get('total_assets')),
            'net_worth': _r2(pos.get('net_worth')),
            'zplay': _r2(act.get('zplay')),
            'wechat': _r2(act.get('wechat')),
            'cash': _r2(act.get('cash')),
            'jianbank': _r2(act.get('jianbank')),
            'gongbank': _r2(act.get('gongbank')),
            'zhongbank': _r2(act.get('zhongbank')),
            'nongbank': _r2(act.get('nongbank')),
            'accumulationfund': _r2(act.get('accumulationfund')),
            'realnum': _r2(pos.get('net_worth')),
            'borrow': _r2(pos.get('borrow')),
            'lend': _r2(pos.get('receivable')),
            'remarks': pos.get('remarks') or '',
        })

    return {
        'items': result_items,
        'total': total,
        'page': page,
        'page_size': page_size,
    }


# 🗑️ `reconcile()`（账面 vs 实际对账）已于 2026-10-03 **退役**，连视图与路由一并下线。
# 判据：**两侧输入源都已退役** ——
#   · 左侧基准 `wealth_balance_list.balance`（流水余额）自 2026-06 停填（恒 NULL
#     ⇒ `book_balance` 恒为 0）；
#   · 右侧 `wealth_cash_flow` 自 v3.60.7 起降级为历史存档。
# 留着只会对 2026-06 之后的期次 **恒报 mismatched**，让用户以为是数据错了。
# 若将来要重做对账：基准侧应改为「资产盘点」(wealth_asset_snapshot + item)，
# 而不是任何一个旧表。详见 `docs/wealth_balance_list-字段退役决策稿-20261003.md`。


def create_or_update_snapshot(data: dict) -> WealthCashFlow:
    """创建或更新现金盘点记录（按 yearmon 定位）

    ⚠️ 这里**不能用 `update_or_create(yearmon=...)`**：旧表允许同期多行
       （2026-06 就有两行），`update_or_create` 内部先 `.get()`，
       同期多行时抛 MultipleObjectsReturned → 用户点「编辑」直接 500。
       改为：取该期**去重后留下的那一行**（btime 最新）更新，没有才新建 ——
       写入与读取用同一条去重规则，才能保证「改完再看，看到的就是刚改的」。
       同期的其它行当历史保留，不在本函数里删（删数据须用户本人执行）。
    """
    yearmon = data.get('yearmon')
    if not yearmon:
        raise ValueError('yearmon is required')
    yearmon = norm_yearmon(yearmon)

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

    existing = next(
        (cf for cf in reversed(get_snapshot_series())
         if norm_yearmon(cf.yearmon) == yearmon),
        None,
    )
    if existing is not None:
        for field, value in defaults.items():
            setattr(existing, field, value)
        existing.save()
        return existing

    return WealthCashFlow.objects.create(yearmon=yearmon, **defaults)


def copy_last_month(yearmon: str) -> WealthCashFlow | None:
    """复制上月（严格小于目标期的最近一期）的盘点数据到指定年月

    改走去重后的序列：原实现用 `annotate(Replace(...))` 比较去掉横杠的串，
    在同期多行的表上会拿到**不确定**的一条（同月两行时「上月」的含义本身就
    要靠去重规则确定）。现在语义明确 = 去重序列里目标期之前的那一期。
    """
    target = norm_yearmon(yearmon)
    earlier = [cf for cf in get_snapshot_series() if norm_yearmon(cf.yearmon) < target]
    if not earlier:
        return None
    last = earlier[-1]

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
