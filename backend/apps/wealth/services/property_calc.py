"""物件资产 · 计算引擎（唯一真源）

本模块是整个「物件资产」的**唯一**算法实现。服务层只负责取数与组装，
视图层一个除法都不做，前端只把数摆出来 —— 口径一旦分散，两处迟早不一致，
而且不一致是**静默**的：两边都能显示出一个看着合理的数字。

四条口径（写死在代码里、也写在 `constants.PROPERTY_METRIC_NOTES` 里给前端看）：

一、主产出是「已用月数 vs 计划月数」，净值只是附带
    给一台 2016 年的空调算「现在值 800 元」没有意义 —— 你不会卖掉它。
    有意义的是「计划用 8 年、已经用了 10 年 2 月」，它一句话回答了该不该换。
    ⇒ 净值不涂色、不告警、不做「健康度」评分；超期只做**中性标注**。
      「用超了」是事实，不是错误，别把它做成红黄绿。

二、净值在报废那刻**定格**
    在用 / 闲置的按「今天」算（它还在折旧）；已报废的按「报废那天」算 ——
    「它值多少」这个答案在报废那刻就固定了，之后不该随日历继续变化。
    报废了却没填日期的，不兜底成今天（那等于假装它今天才报废）。

三、算不出来就说算不出来
    缺金额 / 缺购买日期 / 缺年限 / 购买日期在未来 / 报废了却没填报废日
    → 返回 None + 原因（issues），**不返回 0**。
    0 是「真的折完了」的结论，跟「算不出来」不是一回事 —— 界面上显示 0
    会让这两件事看起来一样，而它们该采取的行动相反（一个该换新，一个该补数据）。

四、年限只在**一个**地方换算
    界面填「年」（支持小数），库里存「月」，换算只走 `years_to_months()`。
    别处不许再写 ``/ 12`` 或 ``* 12`` —— 两处换算迟早不一致，且不一致是静默的。

五、状况是「损坏」⇒ 净值归 0（2026-09-26 订正）
    坏了就不值钱 —— 这一跳**压过**折旧：损坏件不按剩余年限算残值，直接 0.00。
    它只改净值一项：件数照常计入、原值合计照常计入、
    已用 / 计划 / 超期 / 月折旧**全都不动**（那些是时间事实，与好不好使无关）。
    ⚠️ 这一跳**不看**金额 / 年限 / 日期 —— 所以损坏件的净值永远是 0.00，
       不会是「算不出」（None）。理由与第三条不冲突：0 在这里不是兜底，
       而是「坏了 ⇒ 不值钱」这个独立成立的事实。
    ⚠️ 于是 0 有了两个来源：「真的折完了」与「因损坏归零」。
       两者的金额合到同一个数是对的（它现在确实不值钱），
       **但不能都显示成「已折完」** —— 一个该考虑换新、一个该修或该扔。
       ⇒ 由后端下发 `zero_reason` 说清是哪一个，**不让前端拿 condition 自己判断**：
         口径只有一份，前端那份迟早被漏掉，而漏掉是静默的。
    🔴 但它**必须让合计能解释自己**：勾一下「损坏」会让在用净值合计掉一截、
       而「计入件数」纹丝不动，这正是「合计看着小了却没人会去查」的形态。
       ⇒ `summarize` 单独报出 `broken_count`，「因损坏按 0 计」的件数要能念出来。

🔴 派生值一律不落库（净值 / 已用月数 / 剩余月数 / 月折旧），全部由本模块运行时算。
   判据「以后重算得出同样结果吗」→ 能，所以不落库。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ..constants import (
    PROPERTY_CONDITION_BROKEN,
    PROPERTY_ISSUE_LABELS,
    PROPERTY_METRIC_NOTES,
    PROPERTY_MONTHS_PER_YEAR,
    PROPERTY_STATUS_SCRAPPED,
)

# 原因码 —— 前端点开「—」看到的句子来自 constants.PROPERTY_ISSUE_LABELS（唯一真源）
ISSUE_NO_AMOUNT = 'NO_AMOUNT'
ISSUE_NO_PURCHASE_DATE = 'NO_PURCHASE_DATE'
ISSUE_NO_LIFESPAN = 'NO_LIFESPAN'
ISSUE_FUTURE_PURCHASE_DATE = 'FUTURE_PURCHASE_DATE'
ISSUE_NO_SCRAP_DATE = 'NO_SCRAP_DATE'

# 净值恰好为 0 时的**两种来源** —— 界面上必须说清是哪一个：
#   depreciated → 「已折完」：计划年限真的用完了，该考虑换新；
#   broken      → 「损坏归 0」：还没到年限但坏了，该修或者该扔。
# 两者该采取的行动不同，所以不能都写「已折完」——
# 把「坏了」说成「用够了」正是本模块最防的那种**看着合理的错话**。
# ⚠️ 由后端下发，而不是让前端拿 condition 自己判断：口径只有一份，
#    否则下一次改口径时前端那份必然被漏掉，而漏掉是静默的。
ZERO_REASON_DEPRECIATED = 'depreciated'
ZERO_REASON_BROKEN = 'broken'

_TWO_PLACES = Decimal('0.01')
# 损坏件的净值就是它 —— 「坏了 ⇒ 不值钱」是一个结论，不是「算不出」，所以用 0 而不是 None
_ZERO = Decimal('0.00')


def _issue(code: str) -> dict:
    """issue 的统一形状：原因码 + 给人看的一句话。"""
    return {'code': code, 'label': PROPERTY_ISSUE_LABELS.get(code, code)}


def _q2(value: Decimal) -> Decimal:
    """金额保留 2 位 —— 只在**最后一跳**收口，计算过程不提前舍入。"""
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def years_to_months(years) -> int | None:
    """年限换算：界面填「年」（支持小数，8.5 = 8 年 6 月），库里存「月」。

    ⚠️ **唯一的换算入口**。别处不许再写 ``* 12``。
    留空返回 None —— 不返回 0，也不给任何默认值（类别上的默认年限只用于**预填表单**，
    绝不在这里兜底）。
    """
    if years is None or years == '':
        return None
    try:
        return int(round(Decimal(str(years)) * PROPERTY_MONTHS_PER_YEAR))
    except (InvalidOperation, ValueError, TypeError):
        return None


def format_months(months: int | None) -> str:
    """把月数说成人话：「3 年 2 月」/「5 月」/「—」。

    ⚠️ 前端有一份判据相同的实现（展示用，`formatMonths`）—— 两边各自只此一份。
       本函数供后端文案（如提示语）与测试使用。
    """
    if months is None:
        return '—'
    sign = '-' if months < 0 else ''
    total = abs(int(months))
    years, rest = divmod(total, PROPERTY_MONTHS_PER_YEAR)
    if years and rest:
        return f'{sign}{years} 年 {rest} 月'
    if years:
        return f'{sign}{years} 年'
    return f'{sign}{rest} 月'


def months_between(start: date, end: date) -> int:
    """两个日期之间的**整月数**（向下取整，不足一月不算）。

    (y2-y1)*12 + (m2-m1)，若日 d2 < d1 再减 1：
        2024-03-15 → 2026-09-24 = 30 个月
        2024-03-25 → 2026-09-24 = 29 个月（日 24 < 25）

    ⚠️ 用「整月」而不是「天数 ÷ 30」：人填的是年月，答案也该按年月说话 ——
       天数除法会让 3 月 1 日与 3 月 31 日算出同一个数，而它们差一个月。
    """
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def resolve_ref_date(prop, today: date) -> tuple[date | None, list[dict]]:
    """算一件物件的基准日（「算到哪一天」）。

    只有两种取值：
        在用 / 闲置  → 今天（它还在折旧）
        已报废       → 报废那天（净值在那里定格）
    已报废但没填报废日 → 返回 None + NO_SCRAP_DATE，**不兜底成今天**。
    """
    if prop.status != PROPERTY_STATUS_SCRAPPED:
        return today, []
    if prop.scrapped_date is None:
        return None, [_issue(ISSUE_NO_SCRAP_DATE)]
    return prop.scrapped_date, []


def compute_property(prop, today: date | None = None) -> dict:
    """算一件物件的全部派生值。

    返回的字典直接进序列化器、原样下发 —— **没有一个字段需要前端再计算**。
    这是「前端不判算法、不折算」那条纪律的数据面保障。
    """
    today = today or date.today()
    issues: list[dict] = []

    amount = prop.purchase_amount
    purchased = prop.purchase_date
    lifespan = prop.lifespan_months

    # ── ① 基准日 ──
    ref_date, ref_issues = resolve_ref_date(prop, today)
    issues.extend(ref_issues)

    # ── ② 已用月数 ──
    age_months = None
    if purchased is None:
        issues.append(_issue(ISSUE_NO_PURCHASE_DATE))
    elif ref_date is not None:
        if purchased > ref_date:
            # 购买日在未来 —— 允许入库，但算不出（别静默算出一个负数）
            issues.append(_issue(ISSUE_FUTURE_PURCHASE_DATE))
        else:
            age_months = months_between(purchased, ref_date)

    # ── ③ 剩余月数（**可为负**：超期是事实，不是错误） ──
    remaining_months = None
    if lifespan is None:
        issues.append(_issue(ISSUE_NO_LIFESPAN))
    elif age_months is not None:
        remaining_months = lifespan - age_months

    is_overdue = remaining_months is not None and remaining_months < 0
    overdue_months = -remaining_months if is_overdue else 0

    # ── ④ 月折旧与净值 ──
    # 三个前提缺一不可：有金额、有年限（且为正）、已用月数算得出。
    # ⚠️ 任何一项缺失都返回 None —— 绝不拿类别默认年限顶上、绝不按 0 计。
    monthly_depreciation = None
    current_value = None
    if amount is None:
        issues.append(_issue(ISSUE_NO_AMOUNT))
    elif lifespan is None or lifespan <= 0:
        pass                      # NO_LIFESPAN 已在上一步报出，不重复报
    elif age_months is not None:
        raw_dep = amount / Decimal(lifespan)          # 不提前舍入
        raw_value = amount - Decimal(age_months) * raw_dep
        # 截断到 0：折完了就是 0，不出现负数（负净值没有意义）
        current_value = _q2(raw_value) if raw_value > 0 else _ZERO
        monthly_depreciation = _q2(raw_dep)

    # ── ⑤ 状况=损坏 ⇒ 净值归 0（压过上面算出来的折旧值）──
    # ⚠️ 这一跳**放在最后**，因此金额 / 年限 / 日期缺失的 issue 照旧上报 ——
    #    它们仍然影响别的列（已用 / 计划），不能因为净值已经定了 0 就不报。
    # ⚠️ 这一跳**不看**金额 / 年限 / 日期：「坏了就不值钱」独立成立，
    #    缺哪一格都照样是 0.00，而不是「算不出」（None）。
    zero_reason = None
    if prop.condition == PROPERTY_CONDITION_BROKEN:
        current_value = _ZERO
        zero_reason = ZERO_REASON_BROKEN
    elif current_value is not None and current_value == 0:
        # 净值恰好为 0 —— 这是**结论**（折完了），不是缺数据
        zero_reason = ZERO_REASON_DEPRECIATED

    return {
        'age_months': age_months,
        'remaining_months': remaining_months,
        'lifespan_months': lifespan,
        'monthly_depreciation': monthly_depreciation,
        'current_value': current_value,
        'zero_reason': zero_reason,
        'ref_date': ref_date,
        'is_overdue': is_overdue,
        'overdue_months': overdue_months,
        'issues': issues,
    }


def summarize(rows: list[dict]) -> dict:
    """首屏合计口径 —— **不按 0 计**，且每项合计都必须同时给出四个数。

    rows 每项需含：`status` / `condition` / `purchase_amount` / `current_value`
    （后两者可为 None，服务层从 compute_property 的结果里取；
      `condition` 只用于数出「因损坏按 0 计」的件数）。

    🔴 四项缺一不可（total / counted / unpriced_count / unvalued_count）：
       只给总额的话，界面没法把「少算了」摆出来 ——
       总额看着小一点、件数却是全的，两个数都对不上，还没人会去查。
       界面上要并排念出来：「¥12,340 · 计入 18 件（3 件未填金额、2 件未填年限，未计入）」。

    🔴 净值块还多一个 `broken_count`（2026-09-26 随「损坏 ⇒ 净值归 0」一并加的）：
       勾一下「损坏」会让在用净值合计掉一截，而「计入件数」纹丝不动 ——
       总数变小、件数还是全的，正是上面那个「两个数对不上还没人会去查」的形态。
       所以损坏件**照常计入 counted**（它的净值就是 0，是一个结论、不是缺数据），
       但要单独把件数报出来，让界面能说「这几件是按 0 计的」。
    """
    in_use_rows = [r for r in rows if r['status'] != PROPERTY_STATUS_SCRAPPED]
    scrapped_rows = [r for r in rows if r['status'] == PROPERTY_STATUS_SCRAPPED]

    def _sum(values) -> Decimal:
        total = Decimal('0')
        for v in values:
            if v is not None:
                total += v
        return total

    # 原值合计：**含已报废** —— 「这些家当一共投进去多少钱」是历史总投入，
    # 已经淘汰掉的那部分也是花掉的钱（本项不涉及"算不出"，故 unvalued_count 恒为 0）。
    priced_rows = [r for r in rows if r['purchase_amount'] is not None]
    # 在用净值合计：只算还在手上的（在用 + 闲置），报废的已在报废那天定格、不再计入。
    # ⚠️ 损坏件**在这个列表里**（它们的 current_value 是 0.00，不是 None）——
    #    0 是「坏了不值钱」这个结论，不是缺数据，所以照常计入 counted。
    valued_in_use = [r for r in in_use_rows if r['current_value'] is not None]

    return {
        'in_use_count': len(in_use_rows),
        'scrapped_count': len(scrapped_rows),
        'total_amount': {
            'total': _sum(r['purchase_amount'] for r in priced_rows),
            'counted': len(priced_rows),
            'unpriced_count': len(rows) - len(priced_rows),
            'unvalued_count': 0,
        },
        'in_use_net_value': {
            'total': _sum(r['current_value'] for r in valued_in_use),
            'counted': len(valued_in_use),
            # 因损坏被按 0 计的件数 —— 它们**照常计入 counted**，只是金额是 0。
            # ⚠️ 只数**在用 / 闲置**里的：已报废的本来就不进这个合计，
            #    不必在这里重复解释一遍（否则界面上会念出一个与合计无关的数）。
            'broken_count': sum(
                1 for r in in_use_rows if r['condition'] == PROPERTY_CONDITION_BROKEN
            ),
            # 有物件但没填金额 —— 它连原值都没有，自然也无净值
            'unpriced_count': sum(
                1 for r in in_use_rows if r['purchase_amount'] is None
            ),
            # 填了金额却算不出净值（缺日期 / 缺年限 / 日期在未来）
            # ⚠️ 与 broken_count **不重叠**：损坏件一律算得出（就是 0），
            #    所以它永远不会出现在这里 —— 两个数加起来不会超过 counted。
            'unvalued_count': sum(
                1 for r in in_use_rows
                if r['purchase_amount'] is not None and r['current_value'] is None
            ),
        },
    }


def build_metric_meta() -> list[dict]:
    """口径元信息（裸数组）—— 前端气泡直接渲染，零硬编码。

    ⚠️ 与生存资源那边同一条取舍：**不设绝对判定线**（`bands` 恒为空数组）。
       「计划用 8 年、已经用了 10 年 2 月」不是一条判好坏的线，它只是两个数并排摆着 ——
       硬编一条线只会让人以为「超过 X 年就该换」，而那个 X 系统并不知道。
       字段仍然下发，是因为前端气泡组件按同一套结构渲染，少字段会渲染不出来
       （同硬坑⑪：键名写错在界面上看不出来）。
    """
    return [
        {
            'key': key,
            'label': item['label'],
            'unit': item['unit'],
            # 本模块**不据方向上下色** —— 净值高不代表好，超期也不代表坏。
            # 留这个字段只为让组件结构统一。
            'direction': 'neutral',
            'formula': item['formula'],
            'note': list(item['note']),
            'bands': [],
        }
        for key, item in PROPERTY_METRIC_NOTES.items()
    ]
