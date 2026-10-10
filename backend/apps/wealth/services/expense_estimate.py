"""月支出的稳健估计量 —— PERT 三点估算（v3.58.24）

## 为什么需要它

应急金月数的分母是「月支出」。用近 3 个月的算术平均时，**一笔房租或学费
就能让基准翻倍**，月数随之上下跳 —— 用户看到的波动里同时混着
「资产真的变了」和「上个月正好交了学费」两种信息，分不出来。

改用 12 个月样本 + 三点估算：中位数占 4 倍权重（抗极端值），
两端极值各占 1 倍（仍保留「偶尔确实有大额支出」这个事实）。

## 口径

    E = (O + 4M + P) ÷ 6
    O = 窗口内最小月支出，M = 中位数，P = 最大月支出
    窗口 = 锚定月**之前**的 EMERGENCY_EXPENSE_MONTHS 个完整月（不含锚定当月）
    有支出记录的月份 < PERT_MIN_MONTHS 时 value = None（数据不足）

与 `constants.RATIO_BANDS['emergency_months']['note']` 是同一份口径的
两种表述：那边给人看（气泡提示），这边给机器算。**改一处必须改另一处。**

## 两条容易写错的边界

⚠️ **不含锚定当月**。盘点当月往往才过几天（实测 2026-09-08 盘点，
   当月支出仅 477.79），把它算进样本会把基准拉低、月数抬高 ——
   那是往乐观方向错，最不该犯的方向。

⚠️ **支出取数走 classify_service.monthly_classified_totals**，
   即**已剔除「不计入」类型**（转入 / 转出 / 余额变更）的口径。
   转账不是消费，把它算进「月支出」会让应急金月数凭空变短。

🔴 本模块是应急金分母的**唯一实现**。健康指标卡（`cashflow_service`）
   与比率面板（`ratio_service`）都调它 —— 在别处再写一次算术平均，
   同一个「应急金月数」就会在两张卡上给出两个数。
"""

from datetime import datetime
from statistics import median

from apps.wealth.constants import (
    EMERGENCY_EXPENSE_MONTHS,
    PERT_MIN_MONTHS,
    PERT_WEIGHTS,
    PERT_WEIGHT_SUM,
)


def _prev_month_key(ym_key: int) -> int:
    """上一个自然月的 `year*100+month` 键（跨年正确）"""
    year, month = divmod(int(ym_key), 100)
    if month <= 1:
        return (year - 1) * 100 + 12
    return year * 100 + (month - 1)


def window_ym_keys(anchor_key: int, months: int) -> list[int]:
    """锚定月**之前**的 N 个完整月键，新 → 旧，**不含锚定月**。

    例：anchor=202609, months=3 → [202608, 202607, 202606]
    """
    keys: list[int] = []
    cursor = _prev_month_key(anchor_key)
    for _ in range(max(int(months), 1)):
        keys.append(cursor)
        cursor = _prev_month_key(cursor)
    return keys


def _anchor_key(anchor_yearmon) -> int:
    """把锚定月归一成 `year*100+month`；无法定位月份时返回 0（由调用方回落当前月）。

    接受 `'2026-09'` / `'2026-9'` / `'202609'` / `202609` 四种写法。
    ⚠️ 5 位数字（`'2026-9'` 去掉分隔符）必须补零，否则 `2026-9` 与
       `2026-09` 会被当成两期 —— 与 `cashflow_service.norm_yearmon`
       是同一条规则。此处不复用那个函数，是为了避免
       `cashflow_service` 与 `expense_estimate` 互相 import。
    """
    digits = ''.join(ch for ch in str(anchor_yearmon or '') if ch.isdigit())
    if len(digits) == 5:
        return int(digits[:4]) * 100 + int(digits[4:])
    if len(digits) >= 6:
        return int(digits[:6])
    return 0


def _detail_from_buckets(buckets: dict, ym_keys: list[int]) -> list[dict]:
    """从月度归类结果里挑出**有支出记录**的月份。

    ⚠️ 判据是「该月支出 > 0」而非「该月有账单行」：只记了收入却没记支出的
       月份会被当成零支出月份，而 0 一旦进入样本就会顶掉 O（最小值）、
       把基准拉低 —— 那正是「往乐观方向错」。
    """
    detail: list[dict] = []
    for key in ym_keys:
        bucket = buckets.get(key) or buckets.get(str(key)) or {}
        amount = round(float(bucket.get('expense_total') or 0.0), 2)
        if amount <= 0:
            continue
        detail.append({
            'ym_key': key,
            'year': key // 100,
            'month': key % 100,
            'amount': amount,
        })
    return detail


def _estimate_from_detail(detail: list[dict], anchor: int) -> dict:
    """三点估算的主体 —— 只吃「样本月份」与锚定月，**不碰数据库**。

    拆出来的理由见 `estimate_from_buckets`：趋势要为每个点算一次分母，
    不能每点都去查库。
    """
    months_with_records = len(detail)
    base = {
        'window_months': int(EMERGENCY_EXPENSE_MONTHS),
        'months_required': int(PERT_MIN_MONTHS),
        'months_with_records': months_with_records,
        'anchor_yearmon': f'{anchor // 100:04d}-{anchor % 100:02d}',
        'ym_keys': window_ym_keys(anchor, EMERGENCY_EXPENSE_MONTHS),
        'detail': detail,
    }

    if months_with_records < PERT_MIN_MONTHS:
        return {
            **base,
            'value': None,
            'optimistic': None,
            'likely': None,
            'pessimistic': None,
            'mean': None,
            'median': None,
            'reason': (f'窗口内只有 {months_with_records} 个月有支出记录，'
                       f'少于三点估算所需的 {PERT_MIN_MONTHS} 个月'),
        }

    amounts = [d['amount'] for d in detail]
    optimistic = min(amounts)
    likely = float(median(amounts))
    pessimistic = max(amounts)

    # 权重配比在 constants 里 —— 不在这里写 4 与 6，
    # 否则换配比时会出现「常量改了、算式没改」。
    w_o, w_m, w_p = PERT_WEIGHTS
    value = round(
        (w_o * optimistic + w_m * likely + w_p * pessimistic) / PERT_WEIGHT_SUM,
        2,
    )

    return {
        **base,
        'value': value,
        'optimistic': round(optimistic, 2),
        'likely': round(likely, 2),
        'pessimistic': round(pessimistic, 2),
        'mean': round(sum(amounts) / len(amounts), 2),
        'median': round(likely, 2),
        'reason': None,
    }


def estimate_from_buckets(buckets: dict, anchor_key: int) -> dict:
    """用**已取好的**月度归类结果算三点估算。

    为什么必须留这个入口：`get_ratio_trend` 要为每个点各算一次分母，
    若每点都自己去查库就是 N+1（展示 12 个月 = 12 次全窗口查询）。
    趋势本来就已经把整段（含前置 11 个月）的月度归类取好了 ——
    直接复用，零额外查询。
    """
    anchor = _anchor_key(anchor_key)
    if not anchor:
        now = datetime.now()
        anchor = now.year * 100 + now.month
    ym_keys = window_ym_keys(anchor, EMERGENCY_EXPENSE_MONTHS)
    return _estimate_from_detail(_detail_from_buckets(buckets, ym_keys), anchor)


def get_monthly_expense_estimate(user_id: int = 1,
                                 anchor_yearmon=None) -> dict:
    """近 N 个完整月支出的三点估算 → 应急金月数的分母。

    `anchor_yearmon` 为空时锚定「当前自然月」；传快照的 `yearmon`
    则让分母与分子（同期的资产快照）**对齐同一个时点**。

    返回结构::

        {
          'value': 19112.29 | None,   # E —— 应急金分母；None = 数据不足
          'optimistic': 477.79,       # O 最小月
          'likely': 23754.03,         # M 中位数
          'pessimistic': 45514.14,    # P 最大月
          'mean': 26871.04,           # 算术平均（对照用，不参与估算）
          'median': 23754.03,
          'months_with_records': 9, 'months_required': 3,
          'window_months': 12, 'anchor_yearmon': '2026-09',
          'ym_keys': [202608, ...],   # 新 → 旧，含无记录的月份
          'detail': [{'ym_key': .., 'year': .., 'month': .., 'amount': ..}],
          'reason': None | '窗口内只有 2 个月有支出记录…',
        }

    ⚠️ `value` 为 None 表示「算不出来」，**不是 0**。0 是一个结论
       （「月支出为零」⇒ 月数无穷），二者不能混。
    """
    from apps.wealth.services.classify_service import monthly_classified_totals

    anchor = _anchor_key(anchor_yearmon)
    if not anchor:
        now = datetime.now()
        anchor = now.year * 100 + now.month

    ym_keys = window_ym_keys(anchor, EMERGENCY_EXPENSE_MONTHS)
    buckets = monthly_classified_totals(ym_keys, user_id)
    return _estimate_from_detail(_detail_from_buckets(buckets, ym_keys), anchor)
