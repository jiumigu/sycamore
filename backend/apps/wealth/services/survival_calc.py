"""生存资源盘点 · 计算引擎（唯一真源）

本模块是整个「生存资源盘点」的**唯一**算法实现。服务层只负责取数与组装，
视图层一个除法都不做，前端只上色 —— 口径一旦分散，两处迟早不一致，
而且不一致是**静默**的：两边都能显示出一个看着合理的数字。

四条口径（写死在代码里、也写在 `constants.SURVIVAL_METRIC_NOTES` 里给前端看）：

一、一顿饭不是一种东西，但也不是「必须凑齐」
    同餐位（staple）下多种食材**互相替代** → 餐数相加
    跨餐位（required）**缺一不可** → 取最小值（木桶效应只在这里成立）
    ⚠️ 把可替代的主食取最小，会得出「30 顿米粉 + 25 顿面条 = 只能吃 20 顿」。

二、类别聚合只有求和与取最小，**没有算术平均**
    「三样东西各能撑 100 天」既不等于 100 天，也不等于平均 100 天。
    取平均会算出一个毫无意义却看着合理的数 —— 比直接报错更危险。

三、PERT 的输入是**消耗速率**，不是手填天数
    人能回答「一天吃几顿、省着吃几顿」，答不出「这堆米粉最悲观能撑几天」。
    语义铁律：乐观 = 消耗慢 = 撑得久 ⇒ 恒有 O ≥ P、离散度 ≥ 0。
    三档在**被报告的那一层**聚合完再取期望值，不做「先算期望再平均」——
    后者会把 min 语义悄悄换成 mean。

四、算不出来就说算不出来
    单位不可比、配方缺件、没有任何可用物品 → 返回 None + 原因（issues），
    **不返回 0**。0 是「真的撑 0 天」的结论，跟「算不出来」不是一回事。
    配方缺件更不许静默跳过 —— 少一项分母会让这道菜**算得更耐吃**。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..constants import (
    PERT_WEIGHTS,
    PERT_WEIGHT_SUM,
    SURVIVAL_CYCLE_DAYS,
    SURVIVAL_DRIVER_SCENARIOS,
    SURVIVAL_ESSENTIAL_LEVEL_FLOORS,
    SURVIVAL_ESSENTIAL_LEVEL_ORDER,
    SURVIVAL_MEAL_BASELINE,
    SURVIVAL_MEAL_SCENARIOS,
    SURVIVAL_RATE_SCENARIOS,
    SURVIVAL_SATIETY_COUNTED,
    SURVIVAL_SCENARIOS,
    SURVIVAL_STATUS_EXCLUDED,
)

# 行级问题的枚举（前端据此决定是否给「去补配置」的入口）
ISSUE_NO_UNIT = 'no_unit'
ISSUE_UNIT_MISMATCH = 'unit_mismatch'
ISSUE_BAD_QUANTITY = 'bad_quantity'
ISSUE_MISSING_ITEM = 'missing_item'
ISSUE_NO_STOCK = 'no_stock'
ISSUE_EMPTY_RECIPE = 'empty_recipe'
ISSUE_NO_DAYS_PER_UNIT = 'no_days_per_unit'
ISSUE_BAD_CYCLE = 'bad_cycle'
ISSUE_UNKNOWN_MODE = 'unknown_mode'
ISSUE_ORPHAN_ITEM = 'orphan_item'
ISSUE_NO_RECIPE = 'no_recipe'
ISSUE_ESSENTIAL_MISSING = 'essential_missing'
ISSUE_EMPTY_COMBO = 'empty_combo'

ISSUE_LABELS = {
    ISSUE_NO_UNIT: '物品没有指定单位，无法折算',
    ISSUE_UNIT_MISMATCH: '库存单位与用量单位不是同一基准，不可换算',
    ISSUE_BAD_QUANTITY: '每餐用量必须大于零',
    ISSUE_MISSING_ITEM: '引用的物品已不存在',
    ISSUE_NO_STOCK: '库存为零或已过期，不计入可用',
    ISSUE_EMPTY_RECIPE: '配方还没有任何食材',
    ISSUE_NO_DAYS_PER_UNIT: '没填可用时长（按天或按次），算不出能撑多久',
    ISSUE_BAD_CYCLE: '按次计量的「每几个周期」与「每周期几次」都要大于零',
    ISSUE_UNKNOWN_MODE: '未知的消耗模式，无法计算',
    ISSUE_ORPHAN_ITEM: '有食材未纳入任何配方，不计入时长',
    ISSUE_NO_RECIPE: '还没有配餐配方，无法计算能撑多少顿',
    ISSUE_ESSENTIAL_MISSING: '这件必需品还没有对应的库存记录，缺口无从判断',
    ISSUE_EMPTY_COMBO: '这个组合里一件物品都没有，这一行不构成消耗',
}


def _f(value) -> float | None:
    """Decimal / None → float / None（统一出参类型，避免 Decimal 混进 JSON）"""
    if value is None:
        return None
    return float(value)


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


def _issue(code: str, **extra) -> dict:
    """构造一条问题记录 —— 永远是「码 + 可读文本 + 出错对象」，不让前端拼文案"""
    row = {'code': code, 'message': ISSUE_LABELS.get(code, code)}
    row.update(extra)
    return row


# ──────────────────────────────────────────────────────────────
# 单位换算
# ──────────────────────────────────────────────────────────────

def unit_base_name(unit) -> str:
    """单位的基准名：留空表示「自成基准」，用它自己的名字"""
    if unit is None:
        return ''
    return (unit.base_unit or '').strip() or unit.name


def units_comparable(unit_a, unit_b) -> bool:
    """两个单位能不能互相换算

    规则：折到同一个 `base_unit` 才可比。留空 base_unit 的单位自成一系，
    只有当另一方也是同一套（基准名相同）时才可比。

    ⚠️ 不猜换算率。库存按「袋」、配方按「克」而袋子没填「1 袋 = N 克」时，
       唯一的诚实做法是报「单位不可比」—— 猜一个数字会静默给出错误天数。
    """
    if unit_a is None or unit_b is None:
        return False
    if unit_a.pk == unit_b.pk:
        return True
    return unit_base_name(unit_a) == unit_base_name(unit_b)


def to_base(quantity, unit) -> float | None:
    """折算到基准单位；unit 为空返回 None（没单位就没法换算）"""
    if unit is None or quantity is None:
        return None
    rate = unit.to_base_rate if unit.to_base_rate is not None else Decimal(1)
    return float(quantity) * float(rate)


def expiry_cap_days(item, today: date) -> int | None:
    """保质期封顶天数：距离过期还有几天。无过期日 = 不封顶（None）。

    ⚠️ 这是吃与用两类的**硬上限**：库存算出来能撑 200 天，
       但最早那批下月过期，实际就是撑到下月。
    """
    if item is None or getattr(item, 'expire_date', None) is None:
        return None
    return (item.expire_date - today).days


def item_is_usable(item) -> bool:
    """已过期的物品不算可用库存 —— 算进去等于自欺欺人"""
    return getattr(item, 'status', '') not in SURVIVAL_STATUS_EXCLUDED


# ──────────────────────────────────────────────────────────────
# PERT
# ──────────────────────────────────────────────────────────────

def pert_triple(values: dict[str, float | None]) -> dict:
    """三档 → 期望值 + 离散度

    E = (O × 1 + M × 4 + P × 1) ÷ 6，σ = (O − P) ÷ 6
    权重来自 `constants.PERT_WEIGHTS`（与应急金月数同一份），不在此处写死。
    """
    o, m, p = values.get('optimistic'), values.get('likely'), values.get('pessimistic')
    if o is None or m is None or p is None:
        return {'expected': None, 'spread': None}
    wo, wm, wp = PERT_WEIGHTS
    total = o * wo + m * wm + p * wp
    return {
        'expected': _round(total / PERT_WEIGHT_SUM),
        'spread': _round(abs(o - p) / PERT_WEIGHT_SUM),
    }


def scenario_factor(mode: str, scenario: str) -> float | None:
    """取某个消耗模式在某一档下的「消耗速率系数」

    配餐模式返回的是**每日餐数**（直接代入除法），其余模式返回**速率系数**
    （乘在基准速率上）。两者语义不同，故调用方按 mode 分开处理 ——
    统一成一个字段会让「2」到底是 2 餐还是 2 倍永远说不清。
    """
    table = SURVIVAL_DRIVER_SCENARIOS.get(mode)
    if not table:
        return None
    return table.get(scenario)


def meal_count_for(scenario: str, meals_per_day) -> float | None:
    """某档下「每天吃几顿」

    constants 里的三档（省 2 / 常 3 / 放 4）是以**每天 3 餐为基准刻度**给出的；
    配方自己的 meal_per_day 按同一刻度等比缩放 ——
    否则一天只吃一顿的自律期会被按 3 餐/天去扣，天数少算一倍以上。
    """
    base = float(meals_per_day or SURVIVAL_MEAL_BASELINE)
    canonical = SURVIVAL_MEAL_SCENARIOS.get(scenario)
    if canonical is None:
        return None
    return base * canonical / SURVIVAL_MEAL_BASELINE


# ──────────────────────────────────────────────────────────────
# 配方（配餐）计算
# ──────────────────────────────────────────────────────────────

def _item_servings(
    item, quantity_per_serving, unit, today: date,
) -> tuple[float | None, list[dict]]:
    """一件物品按给定用量能供多少顿 —— **唯一实现**

    可支撑餐数 = 折算库存 ÷ 折算每餐用量
    —— 两边都折到基准单位，故「库存存袋、配方按克」也能算（前提是袋子填了换算率）。

    🔴 配方行（`SurvivalRecipeLine`）与组合成员（`SurvivalComboItem`）**共用这一段**：
       各写一遍的话，单位换算与「算不出就说算不出」的口径迟早分叉，
       而**分叉是静默的** —— 两边都会给出一个看着合理的数。

    返回 `(servings, issues)`：算不出时 servings 为 `None`，原因在 issues 里点名。
    """
    issues: list[dict] = []

    if not item_is_usable(item):
        issues.append(_issue(ISSUE_NO_STOCK, item=item.name))
        return None, issues

    # 用量单位：行上没写就跟随物品自己的单位
    line_unit = unit or item.unit
    if item.unit is None or line_unit is None:
        issues.append(_issue(ISSUE_NO_UNIT, item=item.name))
        return None, issues
    if not units_comparable(item.unit, line_unit):
        issues.append(_issue(
            ISSUE_UNIT_MISMATCH, item=item.name,
            detail=f'库存按「{item.unit.name}」（基准 {unit_base_name(item.unit)}），'
                   f'用量按「{line_unit.name}」（基准 {unit_base_name(line_unit)}）',
        ))
        return None, issues

    per_serving = _f(quantity_per_serving)
    if per_serving is None or per_serving <= 0:
        issues.append(_issue(ISSUE_BAD_QUANTITY, item=item.name))
        return None, issues

    stock_in_base = to_base(_f(item.quantity), item.unit)
    need_in_base = to_base(quantity_per_serving, line_unit)
    if not need_in_base:
        issues.append(_issue(ISSUE_BAD_QUANTITY, item=item.name))
        return None, issues

    return _round(stock_in_base / need_in_base), issues


def compute_recipe_line(line, today: date) -> dict:
    """单条配方行（一件食材）的计算底稿"""
    item = line.item
    servings, issues = _item_servings(
        item, line.quantity_per_serving, line.unit, today,
    )
    return {
        # 🔴 聚合用的稳定键：配方行与组合行来自**两张表**，id 空间各自独立、
        #    撞号完全正常。用裸 id 当聚合字典的键，两条不同的行会被合并成一条，
        #    而且合并是**静默**的（数字照样算得出来，只是少了约束）。
        'line_key': f'item-{line.id}',
        'line_kind': 'item',
        'line_id': line.id,
        'combo_id': None,
        'combo_name': None,
        'item_id': item.id,
        'item_name': item.name,
        'role': line.role,
        'quantity_per_serving': _f(line.quantity_per_serving),
        'unit_name': (line.unit.name if line.unit else (item.unit.name if item.unit else '')),
        'stock': _f(item.quantity),
        'stock_unit_name': item.unit.name if item.unit else '',
        'satiety': item.satiety,
        'grade': item.grade,
        'expire_date': str(item.expire_date) if item.expire_date else None,
        'expire_cap_days': expiry_cap_days(item, today),
        'servings': servings,
        # 配方行的短板就是它自己；组合行是**组内那件**（见下）
        'bottleneck_item': item.name,
        'members': [],
        'issues': issues,
    }


def _combo_member_row(member, today: date) -> dict:
    """组合成员的一行底稿 —— 与配方行同一套算法，只是多带用量便于展示"""
    item = member.item
    servings, issues = _item_servings(
        item, member.quantity_per_serving, member.unit, today,
    )
    return {
        'item_id': item.id,
        'item_name': item.name,
        'quantity_per_serving': _f(member.quantity_per_serving),
        'unit_name': (member.unit.name if member.unit else (item.unit.name if item.unit else '')),
        'stock': _f(item.quantity),
        'stock_unit_name': item.unit.name if item.unit else '',
        'expire_date': str(item.expire_date) if item.expire_date else None,
        'expire_cap_days': expiry_cap_days(item, today),
        'servings': servings,
        'issues': issues,
    }


def compute_combo_line(line, today: date) -> dict:
    """配方里的**组合行**：这一顿用的一整份组合能撑多少顿

    组内口径恒为**取最小**（并列缺一不可）—— 四样都要下锅，
    能煮几顿由最先耗尽的那件决定。判据与「基准项挂多件」同源。

    🔴 三件事与配方行**刻意不同**，都是「缺件不许静默」那条判据的落地：

        ① 缺口点名**组内那件具体物品**（`bottleneck_item`），不是组合名 ——
           显示「杂粮粥不够了」用户不知道该去买什么。
        ② 组内**任一件算不出** ⇒ 整行 `servings = None`。
           忽略那一件等于把它当成无限大，这道菜反而**算得更耐吃**。
        ③ 空组合（一件都没挂）单独报 `empty_combo`，不静默当成「无约束」。

    ⚠️ 保质期封顶取组内**最早到期**的那件：整锅粥受最早的原料约束。
    """
    combo = line.combo
    members = list(
        combo.members.select_related('item', 'item__unit', 'unit').order_by('id'),
    )
    detail = {
        'line_key': f'combo-{line.id}',
        'line_kind': 'combo',
        'line_id': line.id,
        'combo_id': combo.id,
        'combo_name': combo.name,
        # ⚠️ 组合行没有「单一物品」，`item_id` 留空 **不是** 缺陷：
        #    顶层这几个字段是给列表页一行一个标题用的，组合行用组合名当标题。
        'item_id': None,
        'item_name': combo.name,
        'role': line.role,
        'quantity_per_serving': None,
        'unit_name': '',
        'stock': None,
        'stock_unit_name': '',
        'satiety': '',
        'grade': '',
        'expire_date': None,
        'expire_cap_days': None,
        'servings': None,
        'bottleneck_item': None,
        'members': [],
        'issues': [],
    }

    if not members:
        detail['issues'].append(_issue(ISSUE_EMPTY_COMBO, items=[combo.name]))
        return detail

    rows = [_combo_member_row(member, today) for member in members]
    detail['members'] = rows
    for row in rows:
        detail['issues'].extend(row['issues'])

    caps = [row['expire_cap_days'] for row in rows if row['expire_cap_days'] is not None]
    detail['expire_cap_days'] = min(caps) if caps else None

    computable = [row for row in rows if row['servings'] is not None]
    if len(computable) != len(rows):
        # 判据：「某条分支会让结果变好」的地方必须显式报出来。
        # 把算不出的那件排除掉，这道菜就能算出一个偏乐观的顿数 —— 那是错的。
        # ⚠️ 不另造一条汇总 issue：逐件的 `issues` 上面已经原样收进来了，
        #    它们各自带着**正确的码与物品名**（同配方行那条路径），
        #    再补一条只会让同一件事在界面上说两遍。
        return detail

    shortest = min(rows, key=lambda row: row['servings'])
    detail['servings'] = shortest['servings']
    detail['bottleneck_item'] = shortest['item_name']
    return detail


def compute_recipe(recipe, today: date) -> dict:
    """一个配方能撑多少顿、多少天

    主食位求和 → 与各必配位取最小 → 除以每日餐数得天数。
    任何一行出问题都计入 `issues`，并把整个配方标记为**不可信**（trustworthy=False）
    —— 缺一项分母会让这道菜算得更耐吃，那是最不该出现的结果。
    """
    lines = list(recipe.lines.select_related('item', 'item__unit', 'unit').all())
    line_details = [compute_recipe_line(line, today) for line in lines]
    # 组合行（v3.59.13）—— 与食材行**同一种底稿形状**，故下游聚合一行都不用改：
    # 主食位求和、必配位取最小、保质期封顶都照旧，只是多了一种行。
    combo_details = [
        compute_combo_line(line, today)
        for line in recipe.combo_lines.select_related('combo').all()
    ]
    line_details.extend(combo_details)

    issues: list[dict] = []
    for row in line_details:
        issues.extend(row['issues'])

    if not line_details:
        issues.append(_issue(ISSUE_EMPTY_RECIPE))

    # 餐位聚合：主食位求和（可替代），必配位取最小（缺一不可）
    # ⚠️ 键一律用 `line_key`（'item-3' / 'combo-1'）而**不是** `line_id`：
    #    两类行来自两张表，id 各自从 1 开始，用裸 id 会把两条不同的行合并成一条。
    staple_servings = [
        row['servings'] for row in line_details
        if row['role'] == 'staple' and row['servings'] is not None
    ]
    required_map: dict[str, float] = {}
    for row in line_details:
        if row['role'] == 'required' and row['servings'] is not None:
            required_map[row['line_key']] = row['servings']

    staple_total: float | None
    if not staple_servings:
        staple_total = None
    else:
        staple_total = sum(staple_servings)

    required_min: float | None
    required_line_key: str | None = None
    if required_map:
        required_line_key = min(required_map, key=lambda k: required_map[k])
        required_min = required_map[required_line_key]
    else:
        required_min = None

    # 配了几行必配位（不论该行算不算得出）。
    # ⚠️ 「一行都没配」与「配了但算不出来」都会让 required_min 为 None，
    #    只靠 required_min 区分不出来，而这两件事的处置完全相反：
    #    前者是**无约束、不影响结论**，后者是**配置有问题**。
    #    界面必须能分开说，否则「没配必配项」会被读成「算不出来」——
    #    而旁边「配方可支撑」又算得出来，两边自相矛盾。
    required_line_count = sum(1 for row in line_details if row['role'] == 'required')

    candidates = [v for v in (staple_total, required_min) if v is not None]
    meals = min(candidates) if candidates else None

    # 短板指向：哪个餐位先把配方卡住
    # ⚠️ 一律取 `bottleneck_item` 而**不是** `item_name`：组合行的那格是
    #    **组内最先耗尽的那件**（「绿豆」），不是组合名（「杂粮粥」）——
    #    显示组合名用户不知道该去买什么。
    bottleneck_role = None
    bottleneck_item = None
    if meals is not None:
        if required_min is not None and meals == required_min:
            bottleneck_role = 'required'
            bottleneck_item = next(
                (r['bottleneck_item'] for r in line_details
                 if r['line_key'] == required_line_key),
                None,
            )
        elif staple_total is not None and meals == staple_total:
            bottleneck_role = 'staple'
            # 主食位里最先耗尽的**那一件**才是要补的东西
            staple_rows = [
                r for r in line_details if r['role'] == 'staple' and r['servings'] is not None
            ]
            if staple_rows:
                bottleneck_item = min(staple_rows, key=lambda r: r['servings'])['bottleneck_item']

    # 保质期封顶：整条配方受最早到期的那一行约束
    caps = [
        row['expire_cap_days'] for row in line_details
        if row['expire_cap_days'] is not None
    ]
    expiry_cap = min(caps) if caps else None

    days: dict[str, float | None] = {}
    uncapped_likely: float | None = None
    for scenario in SURVIVAL_SCENARIOS:
        if meals is None:
            days[scenario] = None
            continue
        per_day = meal_count_for(scenario, recipe.meals_per_day)
        value = meals / per_day if per_day and per_day > 0 else None
        if scenario == 'likely':
            uncapped_likely = value
        if value is not None and expiry_cap is not None:
            value = min(value, float(max(expiry_cap, 0)))
        days[scenario] = _round(value)

    # 每日餐数按基准档取值用于展示；天数三档各自用各自餐数
    per_day_likely = float(recipe.meals_per_day or SURVIVAL_MEAL_BASELINE)

    # 保质期是否**真的**卡住了结果（而不是恰好等于）—— 「封顶了」要能被看出来，
    # 否则用户会以为这就是库存能撑的天数。
    capped = bool(
        expiry_cap is not None and uncapped_likely is not None
        and float(max(expiry_cap, 0)) < uncapped_likely - 1e-6
    )

    return {
        'recipe_id': recipe.id,
        'recipe_name': recipe.name,
        'meals_per_day': _f(recipe.meals_per_day),
        'staple_servings': _round(staple_total),
        'required_servings': _round(required_min),
        'required_line_count': required_line_count,
        'meals': _round(meals),
        'days': days,
        **pert_triple(days),
        'bottleneck_role': bottleneck_role,
        'bottleneck_item': bottleneck_item,
        'expiry_cap_days': expiry_cap,
        'capped_by_expiry': capped,
        'lines': line_details,
        'issues': issues,
        'trustworthy': not issues,
        'per_day_reference': per_day_likely,
    }


# ──────────────────────────────────────────────────────────────
# 非配餐物品（折旧 / 按需 / 时间消耗）
# ──────────────────────────────────────────────────────────────

def use_interval_days(item) -> float | None:
    """按次口径折出来的「多久用一次」（天）

        每次间隔 = 每几个周期 × 一个周期多少天 ÷ 每周期用几次

    读作「每 3 天用 1 次」的三个字段，示例：

        每 3 天用 1 次  → 3 × 1 ÷ 1 = 3.0     （卫生巾）
        每 1 天用 2 次  → 1 × 1 ÷ 2 = 0.5     （牙膏，每天早晚各一次）
        每 1 周用 2 次  → 1 × 7 ÷ 2 = 3.5     （洗衣液，一周洗两次衣服）
        每 1 月用 1 次  → 1 × 30 ÷ 1 = 30.0   （宠物驱虫药）

    ⚠️ 「周期单位 → 天数」的换算**全项目只有这一处**（表在 `SURVIVAL_CYCLE_DAYS`）。
       界面与序列化器都不得自己再乘一遍 —— 两处换算迟早会不一致，
       而且不一致是静默的：两边都会显示一个看着合理的数。

    返回 None 表示填得不合法（次数 ≤ 0 / 周期数 ≤ 0 / 周期单位不认识）。
    """
    if item is None:
        return None
    cycle_days = SURVIVAL_CYCLE_DAYS.get(getattr(item, 'use_cycle_unit', None) or '')
    if not cycle_days:
        return None
    num = _f(getattr(item, 'use_cycle_num', None))
    times = _f(getattr(item, 'use_times', None))
    if num is None or num <= 0 or times is None or times <= 0:
        return None
    return num * float(cycle_days) / times


def resolve_life(item) -> dict:
    """解析一件物品的「一份能用多少天」—— 两条口径二选一

    返回 `{days_per_unit, mode, interval_days, error}`：

        mode   'cycle' 按次 / 'day' 按天 / None 两条都没填
        error  `ISSUE_BAD_CYCLE` / `ISSUE_NO_DAYS_PER_UNIT` / None

    三条判据：

    1. **按次优先。** 两条都填时以按次为准 —— 按次填的是原始量（次数 × 频次），
       按天填的是折算结果；原始量更可信，而且用户改过次数之后，
       按天那个值往往是**忘了同步的旧数**。
    2. **填了按次就不许退回按天。** 频次填坏时若悄悄退回按天口径，
       会给出一个「看着正常」的数，而用户以为系统用的是他刚填的次数 ——
       这种错比直接报错难查得多。
    3. **两条都没填返回 `ISSUE_NO_DAYS_PER_UNIT`**，不是 0 天。
    """
    if item is None:
        return {
            'days_per_unit': None, 'mode': None,
            'interval_days': None, 'error': ISSUE_NO_DAYS_PER_UNIT,
        }

    if getattr(item, 'uses_per_unit', None) is not None:
        uses = _f(item.uses_per_unit)
        interval = use_interval_days(item)
        if uses is None or uses <= 0 or interval is None:
            return {
                'days_per_unit': None, 'mode': 'cycle',
                'interval_days': None, 'error': ISSUE_BAD_CYCLE,
            }
        return {
            'days_per_unit': uses * interval, 'mode': 'cycle',
            'interval_days': interval, 'error': None,
        }

    if getattr(item, 'days_per_unit', None) is not None:
        return {
            'days_per_unit': _f(item.days_per_unit), 'mode': 'day',
            'interval_days': None, 'error': None,
        }

    return {
        'days_per_unit': None, 'mode': None,
        'interval_days': None, 'error': ISSUE_NO_DAYS_PER_UNIT,
    }


def compute_item_life(item, today: date) -> dict:
    """一件非配餐物品能撑多少天（三档）

    一份可用天数由 `resolve_life` 解析（按天直填，或按次折算），再乘数量：

        天数 = 数量 × 一份可用天数 ÷ 消耗速率系数

    乐观档系数 0.8（省着用、消耗慢）→ 天数变长；悲观档 1.3 → 天数变短。
    """
    life = resolve_life(item)
    qty = _f(item.quantity)
    row = {
        'item_id': item.id,
        'name': item.name,
        'quantity': qty,
        'unit_name': item.unit.name if item.unit else '',
        'days_per_unit': _f(item.days_per_unit),
        # 按次口径的四个原话字段（界面回显用，不在前端做任何换算）
        'uses_per_unit': _f(getattr(item, 'uses_per_unit', None)),
        'use_cycle_num': _f(getattr(item, 'use_cycle_num', None)),
        'use_cycle_unit': getattr(item, 'use_cycle_unit', '') or '',
        'use_times': _f(getattr(item, 'use_times', None)),
        # 折算结果：按天口径时等于 days_per_unit，按次口径时是算出来的那份
        'life_mode': life['mode'],
        'days_per_unit_effective': _round(life['days_per_unit'], 2),
        'interval_days': _round(life['interval_days'], 2),
        'hours_per_unit': _f(item.hours_per_unit),
        'satiety': item.satiety,
        'grade': item.grade,
        'status': item.status,
        'expire_date': str(item.expire_date) if item.expire_date else None,
        'expire_cap_days': expiry_cap_days(item, today),
        'stocktake_cycle_days': getattr(item, 'stocktake_cycle_days', None),
        'restock_threshold': _f(getattr(item, 'restock_threshold', None)),
        'days': {s: None for s in SURVIVAL_SCENARIOS},
        'expected': None,
        'spread': None,
        'hours_total': None,
        'issues': [],
    }

    if not item_is_usable(item):
        row['issues'].append(_issue(ISSUE_NO_STOCK, item=item.name))
        return row

    if life['error'] is not None:
        row['issues'].append(_issue(life['error'], item=item.name))
        return row

    # 「还能读多少小时」不随消耗速率变化 —— 它是库存属性，不是节奏属性
    if item.hours_per_unit is not None:
        row['hours_total'] = _round(qty * _f(item.hours_per_unit))

    # ⚠️ 不写 `qty or 0`：数量缺失是数据异常，让它显式 TypeError（500）
    #    比静默算成「0 天」好 —— 后者会被读成「这件东西已经没了」。
    base_days = qty * life['days_per_unit']
    cap = row['expire_cap_days']
    for scenario in SURVIVAL_SCENARIOS:
        factor = float(SURVIVAL_RATE_SCENARIOS[scenario])
        value = base_days / factor
        if cap is not None:
            value = min(value, float(max(cap, 0)))
        row['days'][scenario] = _round(value)

    row.update(pert_triple(row['days']))
    return row


# ──────────────────────────────────────────────────────────────
# 类别聚合
# ──────────────────────────────────────────────────────────────

def _aggregate_scenarios(rows: list[dict], aggregate_mode: str) -> dict[str, float | None]:
    """把多件物品/多个配方的三档天数合成类别的三档天数

    sum：可替代 → 各档分别相加（米粉与面条都能当饭，两条腿并成一条）
    min：并列   → 各档分别取最小（短板决定）
    ⚠️ 不提供「平均」：它算出来的数没有任何语义，却长得像个正常结果。
    """
    out: dict[str, float | None] = {}
    for scenario in SURVIVAL_SCENARIOS:
        values = [
            row['days'][scenario] for row in rows
            if row.get('days', {}).get(scenario) is not None
        ]
        if not values:
            out[scenario] = None
        elif aggregate_mode == 'min':
            out[scenario] = min(values)
        else:
            out[scenario] = sum(values)
    return out


def compute_category(
    category, items: list, recipes: list, today: date,
) -> dict:
    """一个类别的生存时长（三档 + 期望）+ 明细

    分派**只看 category.consume_mode，绝不看类别名** ——
    用户把「吃」改名成「口粮」不该让算法失效。
    """
    mode = category.consume_mode
    aggregate_mode = category.aggregate_mode

    result = {
        'category_id': category.id,
        'name': category.name,
        'icon': category.icon,
        'consume_mode': mode,
        'aggregate_mode': aggregate_mode,
        # 实际生效的聚合口径：配餐类固定「取最小」（详见下方 meal 分支注释）。
        # 界面显示**这个**，否则会写着「求和」而算法取最小 —— 谎报比没有字段更糟。
        'aggregate_mode_effective': 'min' if mode == 'meal' else aggregate_mode,
        'days': {s: None for s in SURVIVAL_SCENARIOS},
        'expected': None,
        'spread': None,
        'usable_item_count': 0,
        'item_count': len(items),
        'items': [],
        'recipes': [],
        'snack_days': None,
        'hours_total': None,
        'issues': [],
        'trustworthy': True,
    }

    if mode not in SURVIVAL_DRIVER_SCENARIOS:
        result['issues'].append(_issue(ISSUE_UNKNOWN_MODE, mode=mode))
        result['trustworthy'] = False
        return result

    # 参与计算的物品：果腹/调味/饮水三个角色才算「能吃的一顿」，
    # 零食单独统计 —— 它顶不了一顿饭，混进分母只是看上去更耐吃。
    # ⚠️ 已过期的同样不算「可用」：usable_item_count 是「有多少件真的在撑着」，
    #    把过期件算进去会让人以为柜子里比实际更有货。
    usable_items = [
        it for it in items
        if (it.satiety in SURVIVAL_SATIETY_COUNTED or not it.satiety)
        and item_is_usable(it)
    ]
    result['usable_item_count'] = len(usable_items)

    if mode == 'meal':
        recipe_rows = [compute_recipe(r, today) for r in recipes]
        result['recipes'] = recipe_rows

        # 配方级的问题**不下沉到类别层**（否则服务层汇总时会重复计一遍）；
        # 类别的可信度由它下面的配方决定 —— 有一个配方配置不全，
        # 这个类别的数字就整体不可信。
        result['trustworthy'] = not any(not row['trustworthy'] for row in recipe_rows)

        # 有库存却没有任何配方的类别算不出时长 —— 这不是「0 天」，
        # 是「还没告诉系统你怎么吃」。必须显式说出来，否则用户会以为
        # 系统把他那一柜子粮食算漏了（其实是的，但要知道原因）。
        countable_items = [it for it in usable_items if it.satiety != 'snack']
        if countable_items and not recipe_rows:
            result['issues'].append(_issue(
                ISSUE_NO_RECIPE,
                detail=f'{len(countable_items)} 件食材还没有编入任何配方，不计入时长',
            ))

        # 编了库存却没进配方的食材 = 白存。这个数字不参与计算，
        # 但**不能被静默吞掉** —— 「看不见的数据」比「错的数据」更危险。
        #
        # ⚠️ 组合行要把**组内每一件**都算进「已编入配方」：只加 `line['item_id']`
        #    会把「只通过组合下锅」的食材（绿豆、薏仁…）误报成孤儿 ——
        #    而那正是本次要做组合的场景，报出来就是纯噪音。
        used_item_ids = set()
        for row in recipe_rows:
            for line in row['lines']:
                if line['item_id'] is not None:
                    used_item_ids.add(line['item_id'])
                for member in line.get('members') or []:
                    used_item_ids.add(member['item_id'])
        orphan = [
            it.name for it in countable_items
            if it.id not in used_item_ids and it.satiety != 'snack'
        ]
        if orphan:
            result['issues'].append(_issue(
                ISSUE_ORPHAN_ITEM,
                items=orphan,
                detail=f'{len(orphan)} 件食材未纳入任何配方：{"、".join(orphan[:5])}',
            ))

        # 配餐类：每个配方都是**每天都要吃到**的一组（早/正餐），
        # 所以跨配方一律取最小 —— 有一个凑不齐，今天就吃不成了。
        # 「两种吃法任选」属于**配方内部**的主食位语义（求和），不是这里；
        # 故此处**刻意不读 aggregate_mode**，免得出现「界面写求和、算法取最小」。
        rows = [row for row in recipe_rows if row['meals'] is not None]
        if rows:
            result['days'] = _aggregate_scenarios(rows, 'min')

        # 零食：自身单独折算，不进主食时长（用期望值与四卡口径一致）
        snack_items = [it for it in items if it.satiety == 'snack']
        if snack_items:
            snack_rows = [compute_item_life(it, today) for it in snack_items]
            snack_triple = _aggregate_scenarios(
                [r for r in snack_rows if r['days']['likely'] is not None], 'sum',
            )
            result['snack_days'] = pert_triple(snack_triple)['expected']
    else:
        item_rows = [compute_item_life(it, today) for it in usable_items]
        result['items'] = item_rows

        for row in item_rows:
            result['issues'].extend(row['issues'])

        rows = [row for row in item_rows if row['days']['likely'] is not None]
        result['trustworthy'] = not any(row['issues'] for row in item_rows)
        result['days'] = _aggregate_scenarios(rows, aggregate_mode)
        # 时间消耗类额外给一个「还能读多少小时」的合计（sum/min 同口径）
        hours = [row['hours_total'] for row in rows if row['hours_total'] is not None]
        if hours:
            result['hours_total'] = _round(
                min(hours) if aggregate_mode == 'min' else sum(hours),
            )

    result.update(pert_triple(result['days']))
    return result


# ──────────────────────────────────────────────────────────────
# 必需品对账（v3.59.7）
# ──────────────────────────────────────────────────────────────

def essential_level(expected: float | None) -> str:
    """覆盖天数 → 档位

    ⚠️ 分档只在**这里**做一次，阈值真源是常量表 `SURVIVAL_ESSENTIAL_LEVEL_FLOORS`。
       前端只按返回的 `level` 上色，**不重算** —— 两处判档迟早不一致，
       而不一致是静默的：两边都会显示出一个看着合理的颜色。
    """
    if expected is None:
        return 'unknown'
    if expected >= SURVIVAL_ESSENTIAL_LEVEL_FLOORS['adequate']:
        return 'adequate'
    if expected >= SURVIVAL_ESSENTIAL_LEVEL_FLOORS['tight']:
        return 'tight'
    return 'critical'


def _essential_item_row(life: dict) -> dict:
    """把一件物品的生命周期结果压成基准项里的「逐件明细」一行

    ⚠️ 刻意只挑对账用得上的字段：`compute_item_life` 的输出里还有按次口径的
       四个原话字段、时长合计等，那些属于物品清单页，塞进来只会让这份明细
       看起来像「又一份物品清单」。
    """
    return {
        'item_id': life['item_id'],
        'item_name': life['name'],
        'item_quantity': life['quantity'],
        'item_unit_name': life['unit_name'],
        'item_status': life['status'],
        'expire_date': life['expire_date'],
        'days': dict(life['days']),
        'expected': life['expected'],
        'level': essential_level(life['expected']),
        'issues': list(life['issues']),
    }


def compute_essential(essential, today: date) -> dict:
    """一条必需品的对账：它挂着的那组物品里**最短的一件**能撑多久、落在哪一档

    🔴 三件事必须分清，合并任意两件都会指向**错误的动作**：

        一件都没挂      → 'missing'  去录入，或确认自己根本用不着（那就删掉这项）
        挂了但算不出    → 'unknown'  去补用量口径；东西已过期也是这一档
        算得出          → 按天数落 critical / tight / adequate

    后两者长得都像「没有数字」，但一个要去录入、一个要去改配置 ——
    一律渲染成「算不出来」会把「还没录」说成「配置出错」，
    令人去改一个本来没坏的东西（同 `required_line_count` 那条教训）。

    🔴 组内多件之间**取最小，不求和**（v3.59.12）——

        一条基准项常常需要几件**并列**才成立：睡衣分夏 / 秋 / 冬、
        卫生巾分日用 / 夜用、鞋分室内 / 室外。冬天没睡衣，
        夏季那件囤十件也不解决。判据与类别口径同源：
        **可替代才求和，并列缺一不可就取最小。**

        取最小是**保守**方向，这一点是有意选的：算错成「虚报缺口」，
        用户在界面上看得见、会去核实；反过来求和错了是「掩盖缺口」，
        静默且危险（「用」类曾被一件洗脸巾撑到 4.5 万天，牙膏剩 5 天没人看见）。

    ⚠️ 三档是**逐档取最小**，不是「挑出最短那件、再抄它的三档」——
       一件有到期日封顶、另一件没有时，两条曲线会交叉
       （A 的乐观档最短、B 的悲观档最短），抄一件必然漏掉另一件的短板。

    ⚠️ 只要**有一件算不出**，整条就报 'unknown'、`expected` 也回到 None ——
       不拿部分数据充完整答案。忽略那一件等于假装它不存在，
       而「漏了什么」正是这把尺子要抓的东西。

    ⚠️ 顶层 `item_*` 这几个字段一律指**代表件**（正常用量下最短的那件），
       逐件明细在 `items` 数组里；`shortest` 汇总用的就是这个代表件的名字。
    """
    items = list(essential.items.all())
    row = {
        'essential_id': essential.id,
        'name': essential.name,
        'category_id': essential.category_id,
        'category_name': essential.category.name if essential.category_id else '',
        'scope': essential.scope,
        'unit_name': essential.unit_name,
        'hint': essential.hint,
        'note': essential.note,
        'sort_order': essential.sort_order,
        'items': [],
        # ↓ 一律指**代表件**（正常用量下最短的那件），逐件明细见上面 `items`
        'item_id': None,
        'item_name': '',
        'item_quantity': None,
        'item_unit_name': '',
        'item_status': '',
        'expire_date': None,
        'days': {s: None for s in SURVIVAL_SCENARIOS},
        'expected': None,
        'spread': None,
        'level': 'missing',
        'issues': [],
    }

    if not items:
        # 「未录入」不是错误、是**待办**：它可能是「我确实没有」，也可能是
        # 「我还没录」。系统不替用户判定，只把这件事显式摆出来。
        row['issues'].append(_issue(ISSUE_ESSENTIAL_MISSING, item=essential.name))
        return row

    lives = [compute_item_life(item, today) for item in items]
    # 排序：正常用量下最短的在前，算不出的排最后 ——
    # 有数字的是**结论**，算不出的是**待办**，两种东西不该混在一起排。
    lives.sort(key=lambda life: (
        life['expected'] is None,
        life['expected'] if life['expected'] is not None else 0.0,
        life['item_id'],
    ))
    row['items'] = [_essential_item_row(life) for life in lives]

    representative = lives[0]
    row['item_id'] = representative['item_id']
    row['item_name'] = representative['name']
    row['item_quantity'] = representative['quantity']
    row['item_unit_name'] = representative['unit_name']
    row['item_status'] = representative['status']
    row['expire_date'] = representative['expire_date']

    uncomputable = [life for life in lives if life['expected'] is None]
    if uncomputable:
        # 把「是**哪几件**、为什么」原样报上去 —— 只说「这条算不出」，
        # 用户还得自己一件件翻过去找是哪件坏了。
        row['issues'] = [
            issue for life in uncomputable for issue in life['issues']
        ]
        row['level'] = 'unknown'
        return row

    row['days'] = {
        scenario: min(life['days'][scenario] for life in lives)
        for scenario in SURVIVAL_SCENARIOS
    }
    row.update(pert_triple(row['days']))
    row['level'] = essential_level(row['expected'])
    return row


def summarize_essentials(rows: list[dict]) -> dict:
    """对账结果的汇总：各档计数 + 尚未闭合的核心项

    🔴 「核心项没录全」是一个**独立的可信度信号**，不是天数 ——
       不能因为牙膏没录就把综合天数打到 0（那会把「还没录」说成「只够撑 0 天」，
       而 0 是「真的撑不了」的结论），但也不能不吭声：
       不吭声，用户会以为这份对账已经过关了。
    """
    level_counts = {level: 0 for level in SURVIVAL_ESSENTIAL_LEVEL_ORDER}
    core_level_counts = {level: 0 for level in SURVIVAL_ESSENTIAL_LEVEL_ORDER}
    for row in rows:
        level_counts[row['level']] = level_counts.get(row['level'], 0) + 1
        if row['scope'] == 'core':
            core_level_counts[row['level']] = core_level_counts.get(row['level'], 0) + 1

    core_rows = [r for r in rows if r['scope'] == 'core']
    # 未录入与待补数据都属于「核心项上还没闭合的缺口」——
    # 两者都要人去补一件事，只是补的东西不同。
    unclosed = [r for r in core_rows if r['level'] in ('missing', 'unknown')]

    return {
        'total': len(rows),
        'core_total': len(core_rows),
        'level_counts': level_counts,
        'core_level_counts': core_level_counts,
        'unclosed_core': [
            {'essential_id': r['essential_id'], 'name': r['name'], 'level': r['level']}
            for r in unclosed
        ],
        'unclosed_core_count': len(unclosed),
        'complete': not unclosed,
    }


def find_essential_shortest(rows: list[dict]) -> dict | None:
    """核心必需品里最先见底的那一件

    ⚠️ 只在**核心**项里挑，且只挑**算得出天数**的：
       改善型（洗脸巾、面膜）见底只是不方便，不会让人活不下去；
       未录入的另在 `unclosed_core` 里点名 —— 混进这里会得到一个
       「0 天」的假短板，而它其实只是「还没录」。
    """
    ranked = [r for r in rows if r['scope'] == 'core' and r['expected'] is not None]
    if not ranked:
        return None
    worst = min(ranked, key=lambda r: r['expected'])
    return {
        'essential_id': worst['essential_id'],
        'name': worst['name'],
        'item_name': worst['item_name'],
        'category_name': worst['category_name'],
        'days': worst['expected'],
        'level': worst['level'],
    }


def essential_sort_key(row: dict) -> tuple:
    """对账列表的排序：该先处理的排最前

    🔴 排的是「该先动哪一件」而不是名字顺序 ——
       一张按字母排的对账表，等于把最要紧的那件藏进中间几行。
       次序 = 核心优先 → 档位严重度（未录入/待补数据最前）→ 天数升序。
    """
    return (
        0 if row['scope'] == 'core' else 1,
        SURVIVAL_ESSENTIAL_LEVEL_ORDER.index(row['level']),
        row['expected'] if row['expected'] is not None else float('inf'),
        row['sort_order'],
        row['essential_id'],
    )


def find_bottleneck(category_results: list[dict]) -> tuple[str | None, float | None]:
    """综合 = 跨类别取最小（吃/穿/用/数字并列，短板决定）

    返回 (短板类别名, 该类别期望天数)。
    """
    valid = [c for c in category_results if c.get('expected') is not None]
    if not valid:
        return None, None
    worst = min(valid, key=lambda c: c['expected'])
    return worst['name'], worst['expected']


def classify_bottleneck(
    asset_days: float | None, cash_days: float | None, tolerance: float,
) -> str:
    """钱这条腿与物这条腿，谁先断

    相差不到 tolerance 就判「均衡」—— 判据是「差得明显吗」而不是「谁大谁小」，
    100 天 vs 105 天说「瓶颈在物」只会让人去补一件根本不缺的东西。
    """
    if asset_days is None and cash_days is None:
        return 'balanced'
    if asset_days is None:
        return 'cash'
    if cash_days is None:
        return 'asset'
    if cash_days < asset_days * tolerance:
        return 'cash'
    if asset_days < cash_days * tolerance:
        return 'asset'
    return 'balanced'


def coverage_pct(days: float | None, start: date | None, end: date | None, today: date) -> dict:
    """三年赎回期覆盖率 = 综合生存天数 ÷ 窗口剩余天数

    ⚠️ 窗口取自赎回期模块自己的起止日期，本模块不另存一份 ——
       两处窗口迟早会改到不一致，而且没人会发现。
    """
    if start is None or end is None:
        return {'pct': None, 'remaining_days': None, 'reason': '赎回期窗口未配置'}
    if today > end:
        return {'pct': None, 'remaining_days': 0, 'reason': '赎回期已结束'}
    if today < start:
        remaining = (end - start).days + 1
        anchor_reason = '赎回期尚未开始，按整段窗口计算'
    else:
        remaining = (end - today).days + 1
        anchor_reason = None
    if remaining <= 0 or days is None:
        return {
            'pct': None,
            'remaining_days': remaining,
            'reason': anchor_reason or '综合生存天数算不出来，无法比',
        }
    return {
        'pct': _round(days / remaining * 100),
        'remaining_days': remaining,
        'reason': anchor_reason,
        'window_start': str(start),
        'window_end': str(end),
    }


def cash_days_from_months(months: float | None) -> float | None:
    """应急金月数 → 天数

    复用 v3.58.24 的三点估算口径（现金类资产 ÷ 近 12 月 PERT 月支出），
    本模块**不新写第二份**「钱能撑多久」。按 30 天/月折算并与口径一起说明。
    """
    if months is None:
        return None
    return _round(float(months) * 30, 0)


def build_metric_meta() -> list[dict]:
    """口径元信息（裸数组）—— 前端气泡直接渲染，零硬编码

    ⚠️ 刻意**不设绝对判定线**（`bands` 恒为空数组）：生存时长问的是
       「还能撑多久、跟钱比哪条腿先断」，不是一个「多少算健康」的阈值。
       真正承当刻度角色的是三档（省着 / 正常 / 放开），那是估算的输入，
       不是一条可以拿来判好坏的线 —— 硬编一条线只会让人以为 30 天算合格。
       字段仍然下发，是因为前端气泡组件按同一套结构渲染，少字段会渲染不出来。
    """
    from ..constants import SURVIVAL_METRIC_NOTES

    return [
        {
            'key': key,
            'label': item['label'],
            'unit': item['unit'],
            'direction': 'higher_better',   # 撑得久总是好的；本模块不据此上色
            'formula': item['formula'],
            'note': list(item['note']),
            'bands': [],
            'target': None,
        }
        for key, item in SURVIVAL_METRIC_NOTES.items()
    ]
