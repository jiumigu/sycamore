"""身上之物 · 计算引擎（唯一真源）

本模块是整个「身上之物」的**唯一**算法实现。服务层只负责取数与组装，
视图层一个判断都不做，前端只把数摆出来 —— 口径一旦分散，两处迟早不一致，
而且不一致是**静默**的：两边都能显示出一个看着合理的值。

三条口径（写死在代码里、也写在 `constants.BODY_METRIC_NOTES` 里给前端看）：

一、🔴 `satisfaction` 为空**不等于**「凑合」
    空有两种来由，必须分开说：
        `no_item`  → 这个位还没有任何东西在用（格子空着是对的）
        `unrated`  → 有东西在用，但还没评过（该去评一次）
    这两件事该采取的行动不同。把它们合并成一个「—」，就是
    「把两种来由说成同一件事」—— 而界面上看起来完全正常。
    ⇒ 由**后端**下发 `satisfaction_blank_reason`，**前端只查表、不自己判**。
      这条与 `property_calc.zero_reason` 完全同源：
      口径只有一份，前端那份迟早被漏掉，而漏掉是静默的。

二、🔴 三把尺子正交、**互不推导**（本模块最容易做错的地方）
    进度 `find_status`  这件事办到哪一步了
    满意 `satisfaction` 现在顶着用的这件称不称心（**主观**）
    归属 `property` / `survival_item`  我用的是哪一件（**事实**）
    ⇒ 「已找到 + 凑合」合法、「寻找中 + 称心」合法、「待寻 + 无关联」合法。
      **不要**在这里写「已找到就说明满意」之类的推导，也不要写反向的。
      （同 treasure §5.3.3「三把尺子并列显示、不做联动判断」。）

三、「没搞定」只有一个判据
    `find_status != 'settled'`。**只有这一个值算搞定** ——
    「定下来了」是办完了；用着称不称心是另一把尺子的事。
    ⚠️ 这个数**必须与清单用同一套筛选**：顶部念的「还有 N 件没搞定」
       与点进去看到的行数，任何时候都得对得上（否则就是「两个数对不上还没人会去查」）。

🔴 派生值一律不落库（`satisfaction_blank_reason` / 四个计数），全部由本模块运行时算。
   判据「以后重算得出同样结果吗」→ 能，所以不落库。
"""

from __future__ import annotations

from ..constants import (
    BODY_BLANK_REASON_LABELS,
    BODY_FIND_STATUS_CHOICES,
    BODY_FIND_STATUS_SETTLED,
    BODY_METRIC_NOTES,
)

# 两种来由的原因码 —— 前端点开那一格看到的句子来自 constants（唯一真源）
BLANK_REASON_NO_ITEM = 'no_item'
BLANK_REASON_UNRATED = 'unrated'


def resolve_blank_reason(need) -> str | None:
    """满意为空时，说清是**哪一种**空；满意有值时返回 None。

    ⚠️ 判据是「**有没有挂东西**」而不是「进度到哪一步」：
       「待寻 + 无关联」与「寻找中 + 无关联」都该是 `no_item`（确实没东西在用）；
       而「已找到 + 挂着那件 + 没评过」才是 `unrated`。
       若改用 `find_status` 判，就会出现「明明挂着一件、却说还没有东西在用」——
       一个看着合理的错话。
    """
    if need.satisfaction:
        return None
    if need.property_id or need.survival_item_id:
        return BLANK_REASON_UNRATED
    return BLANK_REASON_NO_ITEM


def blank_reason_text(code: str | None) -> str:
    """原因码 → 给人看的一句话；取不到时原样返回码（**不返回空串**）。

    空串在界面上就是一个没有提示的空白，比一串英文码更难排查。
    """
    if not code:
        return ''
    return BODY_BLANK_REASON_LABELS.get(code, code)


def summarize(rows: list[dict]) -> dict:
    """顶部计数 —— `rows` 每项需含 `find_status`（服务层从模型上取）。

    ⚠️ 每个枚举值都**必须**有一个键（哪怕恒为 0）：气泡与计数卡按 key 取值，
       少一个键会**静默渲染不出来**，而界面上不会报任何错（硬坑⑪）。
       所以这里从 `BODY_FIND_STATUS_CHOICES` 生成键，而不是手写三个字面量 ——
       将来加一档，计数会自动多一个键，不用记得回来改。
    """
    counts = {value: 0 for value, _ in BODY_FIND_STATUS_CHOICES}
    for row in rows:
        status = row['find_status']
        if status in counts:
            counts[status] += 1
    total = len(rows)
    return {
        **counts,
        'total': total,
        # 🔴 唯一一个「我该做点什么」的数字 —— 判据见文件头第三条
        'pending_count': total - counts[BODY_FIND_STATUS_SETTLED],
    }


def build_metric_meta() -> list[dict]:
    """口径元信息（裸数组）—— 前端气泡直接渲染，零硬编码。

    ⚠️ 与物件资产那边同一条取舍：**不设绝对判定线**（`bands` 恒为空数组）。
       这里没有一个「超过 X 条没搞定就不健康」的线 —— 位是你自己列的，
       几条算多只有你知道。字段仍然下发，是因为前端气泡组件按同一套结构渲染，
       少字段会渲染不出来（同硬坑⑪）。
    """
    return [
        {
            'key': key,
            'label': item['label'],
            'unit': item['unit'],
            # 本模块**不据方向上下色** —— 没搞定不代表坏，称心也不代表好。
            # 留这个字段只为让组件结构统一。
            'direction': 'neutral',
            'formula': item['formula'],
            'note': list(item['note']),
            'bands': [],
        }
        for key, item in BODY_METRIC_NOTES.items()
    ]
