"""生存资源盘点 · 服务层

视图层只做协议转换，业务口径全在这里与 `survival_calc` 里：
    · CRUD 的合法性判断（删类别前先看有没有东西、删单位前先看有没有人在用）
    · 综合分析（各类别时长 + 短板 + 双腿对照 + 三年覆盖率）
    · 默认类别种子（幂等）

三条刻意的取舍：

一、**派生值不落库**。可支撑餐数、PERT 期望值、类别时长全部运行时算 ——
    库存与用量随时会改，落库的派生值一旦忘了重算就成了没人会发现的脏数据。

二、**删除一律先问再删，不级联**。删类别要求先清空其下物品与配方；
    删单位要求先解除引用。级联删除会让「删一个空类别」和
    「删掉整柜粮食」用同一个按钮，代价不对称 —— 而这种错误不可逆。

三、「钱能撑多久」**复用应急金月数的三点估算**，本模块不新写第二份口径。
    读 `WealthCurrentScenario.support_weeks` 是错的：那是落库的推演缓存，
    用户不动推演它就永远是旧值，看着像实时数字其实是历史快照。

四、**「够撑多久」与「漏了什么」是两把尺子**（v3.59.7）。
    前者按消耗速率折算天数，后者是必需品基准清单的逐项对账
    （见 `survival_essential_service`）。两者**刻意不互相代入**：
    没录入的牙膏不参与天数计算（那会把「还没录」说成「只够 0 天」），
    但它会在对账里被点名，并让 `essentials.summary.complete` 为假 ——
    用户该看到的是「结论还没闭环」，不是「天赋点 0 天」。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone

from ..constants import (
    SURVIVAL_BOTTLENECK_LABELS,
    SURVIVAL_BOTTLENECK_TOLERANCE,
    SURVIVAL_CATEGORY_SEEDS,
    SURVIVAL_DAYS_PER_YEAR,
    SURVIVAL_ESSENTIAL_LEVELS,
    SURVIVAL_MEAL_SCENARIOS,
    SURVIVAL_SATIETY_COUNTED,
    SURVIVAL_SCENARIOS,
    SURVIVAL_USE_CYCLE_CHOICES,
    SURVIVAL_WEAR_REFERENCE,
)
from ..models import (
    SurvivalCategory,
    SurvivalCombo,
    SurvivalEssential,
    SurvivalItem,
    SurvivalRecipe,
    SurvivalRecipeComboLine,
    SurvivalRecipeLine,
    SurvivalUnit,
)
from . import survival_calc as calc
# 🔴 库存的**唯一写口**（v3.60.18）。本模块不再自己 `item.quantity = …; save()` ——
#    任何绕过 `record_flow` 的库存写入都会造出「无痕变化」：账变了、流水里没有，
#    而界面看起来完全正常。
from .survival_flow import record_flow

MIGRATION_HINT = (
    '生存资源盘点的数据表尚未建立，请先执行迁移：'
    'cd backend && ../.venv/bin/python manage.py migrate wealth'
)


def _today(reference: date | None = None) -> date:
    return reference or timezone.localdate()


# ──────────────────────────────────────────────────────────────
# 读：类别 / 单位
# ──────────────────────────────────────────────────────────────

def _unit_row(unit: SurvivalUnit) -> dict:
    return {
        'id': unit.id,
        'category_id': unit.category_id,
        'name': unit.name,
        'base_unit': unit.base_unit,
        'to_base_rate': float(unit.to_base_rate),
        'is_serving_unit': unit.is_serving_unit,
        'note': unit.note,
        'sort_order': unit.sort_order,
    }


def _category_row(category: SurvivalCategory, with_units: bool = False) -> dict:
    row = {
        'id': category.id,
        'name': category.name,
        'consume_mode': category.consume_mode,
        'consume_mode_label': category.get_consume_mode_display(),
        'aggregate_mode': category.aggregate_mode,
        'aggregate_mode_label': category.get_aggregate_mode_display(),
        # 实际生效的口径：配餐类固定取最小；界面显示这个，不显示用户填进去的那个
        'aggregate_mode_effective': 'min' if category.consume_mode == 'meal' else category.aggregate_mode,
        'icon': category.icon,
        'description': category.description,
        'sort_order': category.sort_order,
        'item_count': category.items.count(),
        'recipe_count': category.recipes.count(),
    }
    if with_units:
        row['units'] = [
            _unit_row(u) for u in category.units.all().order_by('sort_order', 'id')
        ]
    return row


def get_category_list(include_units: bool = False) -> list[dict]:
    rows = SurvivalCategory.objects.filter(user_id=1).order_by('sort_order', 'id')
    return [_category_row(c, with_units=include_units) for c in rows]


def get_unit_list(category_id: int | None = None) -> list[dict]:
    qs = SurvivalUnit.objects.filter(user_id=1)
    if category_id:
        qs = qs.filter(category_id=category_id)
    return [_unit_row(u) for u in qs.order_by('category_id', 'sort_order', 'id')]


def _resolve_category(category_id) -> SurvivalCategory | None:
    """按 id 或名称取类别 —— 允许名称入参是为了让接口可读、便于脚本化"""
    if category_id in (None, ''):
        return None
    if str(category_id).isdigit():
        return SurvivalCategory.objects.filter(id=int(category_id), user_id=1).first()
    return SurvivalCategory.objects.filter(name=str(category_id), user_id=1).first()


# ──────────────────────────────────────────────────────────────
# 读：物品 / 配方
# ──────────────────────────────────────────────────────────────

def _item_row(item: SurvivalItem) -> dict:
    # 一份可用天数走 calc 的唯一实现（按天直填 / 按次折算），服务层不自己算 ——
    # 两处都算的话，界面显示的天数会与类别卡片里的天数不一致，且没人会发现。
    life = calc.resolve_life(item)
    return {
        'id': item.id,
        'category_id': item.category_id,
        'category_name': item.category.name,
        'name': item.name,
        'quantity': float(item.quantity),
        'unit_id': item.unit_id,
        'unit_name': item.unit.name if item.unit else '',
        'satiety': item.satiety,
        'satiety_label': item.get_satiety_display() if item.satiety else '',
        'grade': item.grade,
        'grade_label': item.get_grade_display() if item.grade else '',
        'status': item.status,
        'status_label': item.get_status_display(),
        'priority': item.priority,
        'priority_label': item.get_priority_display() if item.priority else '',
        'days_per_unit': float(item.days_per_unit) if item.days_per_unit is not None else None,
        # 按次计量的四个「原话」字段 —— 下发原值，让界面自己拼
        # 「每 3 天用 1 次」，不做任何换算（换算是 calc 独一份的活）。
        'uses_per_unit': float(item.uses_per_unit) if item.uses_per_unit is not None else None,
        'use_cycle_num': float(item.use_cycle_num) if item.use_cycle_num is not None else None,
        'use_cycle_unit': item.use_cycle_unit or '',
        'use_cycle_unit_label': (
            item.get_use_cycle_unit_display() if item.use_cycle_unit else ''
        ),
        'use_times': float(item.use_times) if item.use_times is not None else None,
        # ⚠️ 显示「一份可用」时必须用 effective：直接显示 days_per_unit
        #    会让按次计量的物品看起来「什么都没填」。
        'life_mode': life['mode'],
        'days_per_unit_effective': (
            round(life['days_per_unit'], 2) if life['days_per_unit'] is not None else None
        ),
        'stocktake_cycle_days': item.stocktake_cycle_days,
        'restock_threshold': (
            float(item.restock_threshold) if item.restock_threshold is not None else None
        ),
        'hours_per_unit': float(item.hours_per_unit) if item.hours_per_unit is not None else None,
        'expire_date': str(item.expire_date) if item.expire_date else None,
        'purchase_date': str(item.purchase_date) if item.purchase_date else None,
        'purchase_cost': float(item.purchase_cost) if item.purchase_cost is not None else None,
        'notes': item.notes,
        'tags': item.tags or [],
        'recipe_line_count': item.recipe_lines.count(),
    }


def get_item_list(
    category_id: int | None = None,
    satiety: str | None = None,
    status: str | None = None,
) -> list[dict]:
    qs = SurvivalItem.objects.filter(user_id=1).select_related('category', 'unit')
    if category_id:
        qs = qs.filter(category_id=category_id)
    if satiety:
        qs = qs.filter(satiety=satiety)
    if status:
        qs = qs.filter(status=status)
    # 排序在服务层给：managed 表不设 Meta.ordering（项目硬坑②），
    # 而这里 order_by 是显式的、不会被注入进聚合里。
    return [_item_row(i) for i in qs.order_by('category_id', 'status', 'name')]


def _line_row(line: SurvivalRecipeLine) -> dict:
    return {
        'id': line.id,
        'item_id': line.item_id,
        'item_name': line.item.name,
        'item_quantity': float(line.item.quantity),
        'item_unit_id': line.item.unit_id,
        'item_unit_name': line.item.unit.name if line.item.unit else '',
        'satiety': line.item.satiety,
        'role': line.role,
        'role_label': line.get_role_display(),
        'quantity_per_serving': float(line.quantity_per_serving),
        'unit_id': line.unit_id,
        'unit_name': line.unit.name if line.unit else '',
        'note': line.note,
    }


def _combo_line_row(line: SurvivalRecipeComboLine) -> dict:
    """配方里的组合行（v3.59.13）

    ⚠️ 字段名与食材行**刻意不同**（`combo_id` / `combo_name` / `members`），
       不硬凑成同一个形状：两者的「每餐用量」来路不同 ——
       食材行在自己身上，组合行的用量在**成员**上。
       前端因此能一眼看出这一行该渲染成组合行，而不必靠「有没有 item_id」猜。
    """
    return {
        'id': line.id,
        'combo_id': line.combo_id,
        'combo_name': line.combo.name,
        'role': line.role,
        'role_label': line.get_role_display(),
        'member_count': line.combo.members.count(),
        'note': line.note,
    }


def _recipe_row(recipe: SurvivalRecipe, with_lines: bool = True) -> dict:
    row = {
        'id': recipe.id,
        'category_id': recipe.category_id,
        'category_name': recipe.category.name,
        'name': recipe.name,
        'meals_per_day': float(recipe.meals_per_day),
        'note': recipe.note,
        'sort_order': recipe.sort_order,
        'line_count': recipe.lines.count(),
        'combo_line_count': recipe.combo_lines.count(),
    }
    if with_lines:
        row['lines'] = [
            _line_row(line)
            for line in recipe.lines.select_related('item', 'item__unit', 'unit').order_by('role', 'id')
        ]
        row['combo_lines'] = [
            _combo_line_row(line)
            for line in recipe.combo_lines.select_related('combo').order_by('role', 'id')
        ]
    return row


def get_recipe_list(category_id: int | None = None, with_lines: bool = True) -> list[dict]:
    qs = SurvivalRecipe.objects.filter(user_id=1).select_related('category')
    if category_id:
        qs = qs.filter(category_id=category_id)
    return [_recipe_row(r, with_lines=with_lines) for r in qs.order_by('category_id', 'sort_order', 'id')]


# ──────────────────────────────────────────────────────────────
# 写：类别 / 单位
# ──────────────────────────────────────────────────────────────

def create_category(payload: dict) -> dict:
    category = SurvivalCategory.objects.create(user_id=1, **payload)
    return _category_row(category, with_units=True)


def update_category(pk: int, payload: dict) -> dict:
    category = SurvivalCategory.objects.get(id=pk, user_id=1)
    for key, value in payload.items():
        setattr(category, key, value)
    category.save()
    return _category_row(category, with_units=True)


def delete_category(pk: int) -> int:
    """删除类别 —— **先看里面有没有东西**，不级联

    级联删除会让「删掉一个建错的空类别」与「删掉整柜粮食」走同一个按钮，
    而代价完全不对称、且不可逆。这里宁可多一步。
    """
    category = SurvivalCategory.objects.get(id=pk, user_id=1)
    item_count = category.items.count()
    recipe_count = category.recipes.count()
    unit_count = category.units.count()
    # 组合也在这个类别底下（v3.59.13）—— 漏了它，删类别会**静默连带删掉组合**，
    # 而组合可能正被别的配方引用（那会连带把配方行也带走）。
    combo_count = category.combos.count()
    if item_count or recipe_count or unit_count or combo_count:
        raise ValueError(
            f'「{category.name}」下还有 {item_count} 件物品、{recipe_count} 个配方、'
            f'{unit_count} 个单位、{combo_count} 个组合，不能直接删除；'
            f'请先清空该类别下的内容。',
        )
    category.delete()
    return pk


def create_unit(payload: dict) -> dict:
    category = SurvivalCategory.objects.get(id=payload.pop('category_id'), user_id=1)
    unit = SurvivalUnit.objects.create(user_id=1, category=category, **payload)
    return _unit_row(unit)


def update_unit(pk: int, payload: dict) -> dict:
    unit = SurvivalUnit.objects.get(id=pk, user_id=1)
    if 'category_id' in payload:
        unit.category = SurvivalCategory.objects.get(id=payload.pop('category_id'), user_id=1)
    for key, value in payload.items():
        setattr(unit, key, value)
    unit.save()
    return _unit_row(unit)


def delete_unit(pk: int) -> int:
    unit = SurvivalUnit.objects.get(id=pk, user_id=1)
    used_by_items = unit.items.count()
    used_by_lines = unit.recipe_lines.count()
    # ⚠️ 组合成员的用量单位也算引用（v3.59.13）：漏了这一处，
    #    `unit.delete()` 会抛 ProtectedError 变成 500，而界面上只显示「删除失败」。
    used_by_combos = unit.combo_members.count()
    if used_by_items or used_by_lines or used_by_combos:
        raise ValueError(
            f'单位「{unit.name}」仍被 {used_by_items} 件物品、{used_by_lines} 条配方行、'
            f'{used_by_combos} 条组合成员使用，不能删除；请先把它们换成别的单位。',
        )
    unit.delete()
    return pk


# ──────────────────────────────────────────────────────────────
# 写：物品 / 配方
# ──────────────────────────────────────────────────────────────

def create_item(payload: dict) -> dict:
    category = SurvivalCategory.objects.get(id=payload.pop('category_id'), user_id=1)

    # 建档时的初始数量**也要留痕**（channel='create'）：否则第一笔库存是
    # 「凭空出现」的，之后任何一次对账都解释不了它从哪来。
    # 做法是先按 0 建、再经唯一写口把它抬到初值 —— 这样流水才有 item_id 可指。
    raw_qty = payload.pop('quantity', None)
    try:
        initial = Decimal('0') if raw_qty in (None, '') else Decimal(str(raw_qty))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('数量必须是数字')
    if initial < 0:
        raise ValueError('数量不能是负数')

    with transaction.atomic():
        item = SurvivalItem.objects.create(
            user_id=1, category=category, quantity=0, **payload,
        )
        if initial != 0:
            record_flow(
                item.id, initial, channel='create', reason='other',
                note='建档时的初始数量', user_id=1,
            )
            item.refresh_from_db()
    return _item_row(item)


def update_item(pk: int, payload: dict) -> dict:
    item = SurvivalItem.objects.get(id=pk, user_id=1)
    if 'category_id' in payload:
        item.category = SurvivalCategory.objects.get(id=payload.pop('category_id'), user_id=1)

    # 数量单独摘出来交给唯一写口 —— 其余字段照常直接改。
    # ⚠️ 这里**不能**顺手把 quantity setattr 进去：那会绕过流水，
    #    造出一次「账变了但没记录」的编辑（铁律一）。
    raw_qty = payload.pop('quantity', None)
    for key, value in payload.items():
        setattr(item, key, value)

    with transaction.atomic():
        item.save()
        if raw_qty is not None:
            try:
                new_qty = Decimal(str(raw_qty))
            except (InvalidOperation, ValueError, TypeError):
                raise ValueError('数量必须是数字')
            delta = new_qty - item.quantity
            if delta != 0:
                # 用户是被动方：他只是在编辑物品，不该被要求再解释一遍为什么
                # 数量变了 —— 渠道 `edit` 由系统填，留痕的代价是 0 次额外输入。
                record_flow(
                    item.id, delta, channel='edit', reason='other',
                    note='直接编辑物品改了数量', user_id=1,
                )
                item.refresh_from_db()
    return _item_row(item)


def delete_item(pk: int) -> int:
    item = SurvivalItem.objects.get(id=pk, user_id=1)
    used = item.recipe_lines.count()
    # ⚠️ 组合成员也算引用（v3.59.13），两处都要看：
    #    只查配方行的话，`item.delete()` 会抛 ProtectedError 变成 500。
    used_by_combos = item.combo_members.count()
    if used or used_by_combos:
        raise ValueError(
            f'「{item.name}」还被 {used} 个配方、{used_by_combos} 个组合引用，不能直接删除；'
            f'请先从配方与组合里移除它。',
        )
    item.delete()
    return pk


# ──────────────────────────────────────────────────────────────
# 试算：把表单里的数**原样**算一遍，但不落库（v3.59.11）
# ──────────────────────────────────────────────────────────────

# ⚠️ `compute_item_life` 读的**每一个**属性都要在这里给全。
#    少给一个不是「按缺省算」而是 AttributeError，且它只会在某条从没被点过的
#    分支上炸 —— 所以这份默认值是按「读什么给什么」逐个对齐出来的，不是随手写的。
_PREVIEW_DEFAULTS = {
    'id': None,
    'name': '',
    'quantity': 0,
    'unit': None,
    'satiety': '',
    'grade': '',
    'status': 'stocked',
    'days_per_unit': None,
    'hours_per_unit': None,
    'uses_per_unit': None,
    'use_cycle_num': None,
    'use_cycle_unit': None,
    'use_times': None,
    'expire_date': None,
    'stocktake_cycle_days': None,
    'restock_threshold': None,
}


def preview_item_life(payload: dict, reference: date | None = None) -> dict:
    """保存前试算一件物品能撑多久 —— **不写库**

    🔴 存在的唯一理由是「不让第二份公式出现」。
       前端当然可以自己把 `数量 × 一份能用几次 ÷ 每天几次` 乘一遍、立刻给出结果，
       但那份公式与 `survival_calc` 迟早会分叉，而**分叉是静默的**：
       试算说 150 天、保存后表里写着 123.7 年，两边看起来都像个正常的数，
       没有任何一处会报错。所以这里刻意不写新逻辑 ——
       造一个只活在内存里的物品，交给 `compute_item_life` 去算，
       与保存后列表里跑的是**同一行代码**。

    ⚠️ 配餐类（`consume_mode='meal'`）直接拒绝：那类物品的时长由配方决定，
       按单件口径算出来的是一个没人核对过的数 —— 而它看着完全合理。
    """
    payload = dict(payload)
    category_id = payload.get('category_id')
    if category_id:
        category = SurvivalCategory.objects.filter(id=category_id, user_id=1).first()
        if category is not None and category.consume_mode == 'meal':
            raise ValueError('配餐类的时长由配方决定，单件试算没有意义')

    unit = None
    if payload.get('unit_id'):
        unit = SurvivalUnit.objects.filter(id=payload['unit_id']).first()

    fields = dict(_PREVIEW_DEFAULTS)
    fields.update({key: value for key, value in payload.items() if key in fields})
    fields['unit'] = unit

    return calc.compute_item_life(SimpleNamespace(**fields), _today(reference))


@transaction.atomic
def create_recipe(payload: dict) -> dict:
    """新建配方（含配方行 + 组合行）。

    整体放进一个事务：配方建好了但配方行没建，会得到一个
    「存在但算不出来」的空配方，而用户以为自己配好了。
    """
    data = dict(payload)
    lines = data.pop('lines', []) or []
    combo_lines = data.pop('combo_lines', []) or []
    category = SurvivalCategory.objects.get(id=data.pop('category_id'), user_id=1)
    recipe = SurvivalRecipe.objects.create(user_id=1, category=category, **data)
    _replace_lines(recipe, lines)
    _replace_combo_lines(recipe, combo_lines, category)
    return _recipe_row(recipe)


@transaction.atomic
def update_recipe(pk: int, payload: dict) -> dict:
    """更新配方 —— 配方行**全删重建**

    与项目里其它主子表一致（如旅行计划）：逐行 diff 的复杂度换不来什么，
    而「删了两行、改了一行、顺序变了」在重建语义下就是一次写操作。

    ⚠️ 组合行与食材行**各自独立判定「这次动没动」**：
       只传 `lines` 不传 `combo_lines` 时，组合行必须原样留着 ——
       一律清空会让「懒得传」变成「静默删掉」。两条都是 `None` 才表示不动。
    """
    recipe = SurvivalRecipe.objects.get(id=pk, user_id=1)
    data = dict(payload)
    if 'category_id' in data:
        recipe.category = SurvivalCategory.objects.get(id=data.pop('category_id'), user_id=1)
    lines = data.pop('lines', None)
    combo_lines = data.pop('combo_lines', None)
    for key, value in data.items():
        setattr(recipe, key, value)
    recipe.save()
    if lines is not None:
        _replace_lines(recipe, lines)
    if combo_lines is not None:
        _replace_combo_lines(recipe, combo_lines, recipe.category)
    return _recipe_row(recipe)


def _replace_lines(recipe: SurvivalRecipe, lines: list[dict]) -> None:
    recipe.lines.all().delete()
    for raw in lines:
        SurvivalRecipeLine.objects.create(
            recipe=recipe,
            item=SurvivalItem.objects.get(id=raw['item_id'], user_id=1),
            role=raw.get('role') or 'staple',
            quantity_per_serving=raw['quantity_per_serving'],
            unit_id=raw.get('unit_id') or None,
            note=raw.get('note') or '',
        )


def _replace_combo_lines(
    recipe: SurvivalRecipe, combo_lines: list[dict], category: SurvivalCategory,
) -> None:
    """组合行全删重建

    ⚠️ 组合必须与配方**同类别**：跨类别的组合意味着「吃」的配方引用了
       「用」类的物品 —— 与上面食材行那条校验同源，两边判据必须一样。
    ⚠️ `UNIQUE(recipe, combo)` 是 DB 层的约束，调用方不保证：
       同一组合挂两次会在落库时 `IntegrityError` → 500。
       **静默去重**（而不是报错）在这里是对的 —— 挂两次的结果与挂一次完全一样
       （组合内部没有倍率），报错只会让人觉得系统在挑刺。
    """
    recipe.combo_lines.all().delete()
    seen: set[int] = set()
    for raw in combo_lines:
        combo = SurvivalCombo.objects.get(id=raw['combo_id'], user_id=1)
        if combo.category_id != category.id:
            raise ValueError(
                f'组合「{combo.name}」不属于「{category.name}」类别，不能编进这个配方',
            )
        if combo.id in seen:
            continue
        seen.add(combo.id)
        SurvivalRecipeComboLine.objects.create(
            recipe=recipe,
            combo=combo,
            role=raw.get('role') or 'staple',
            note=raw.get('note') or '',
        )


def delete_recipe(pk: int) -> int:
    recipe = SurvivalRecipe.objects.get(id=pk, user_id=1)
    recipe.delete()
    return pk


# ──────────────────────────────────────────────────────────────
# 综合分析
# ──────────────────────────────────────────────────────────────

def _empty_analysis(reason: str) -> dict:
    return {
        'available': False,
        'reason': reason,
        'as_of': str(timezone.localdate()),
        'categories': [],
        'shortest_category': None,
        'shortest_days': None,
        'overall': {'days': {}, 'expected': None, 'spread': None},
        'cash': {'months': None, 'days': None, 'basis': ''},
        'bottleneck': 'balanced',
        'bottleneck_label': SURVIVAL_BOTTLENECK_LABELS['balanced'],
        'coverage': {'pct': None, 'remaining_days': None, 'reason': reason},
        'issues': [],
        'snack_days': None,
        'has_any_item': False,
    }


def get_analysis(reference_date: date | None = None) -> dict:
    """综合分析：各类别生存时长 → 短板 → 与钱对照 → 三年覆盖率

    ⚠️ 表尚未建立时返回 `available=False` + 可照做的提示，而不是抛 500：
       「迁移没跑」是可预期的部署状态，不是服务端错误。
    """
    today = _today(reference_date)
    try:
        categories = list(
            SurvivalCategory.objects.filter(user_id=1).order_by('sort_order', 'id')
        )
        result_rows = []
        for category in categories:
            items = list(
                category.items.select_related('unit').order_by('name')
            )
            recipes = list(category.recipes.prefetch_related(
                'lines__item__unit', 'lines__unit',
            ).order_by('sort_order', 'id')) if category.consume_mode == 'meal' else []
            result_rows.append(calc.compute_category(category, items, recipes, today))

        # 必需品对账（v3.59.7）—— 放在同一个 try 里：基准表与类别表是同一批迁移，
        # 表不在时两个查询都会炸，分成两段只会让「迁移没跑」出现两种错误长相。
        from .survival_essential_service import get_reconcile as get_essential_reconcile

        essentials = get_essential_reconcile(today)
    except OperationalError:
        return _empty_analysis(MIGRATION_HINT)

    shortest_name, shortest_days = calc.find_bottleneck(result_rows)

    # 综合口径 = 跨类别取最小（吃/穿/用/数字并列，短板决定）。
    # 与类别内部不同：类别内部可以「可替代求和」，但类别之间不能 ——
    # 有饭吃不能替代没衣穿。
    overall_days = {}
    for scenario in SURVIVAL_SCENARIOS:
        values = [r['days'][scenario] for r in result_rows if r['days'].get(scenario) is not None]
        overall_days[scenario] = min(values) if values else None

    cash_months, cash_basis = _cash_months()
    cash_days = calc.cash_days_from_months(cash_months)

    bottleneck = calc.classify_bottleneck(
        shortest_days, cash_days, SURVIVAL_BOTTLENECK_TOLERANCE,
    )

    coverage = calc.coverage_pct(shortest_days, *_redemption_window(), today)

    # 问题分两级收集：配方级的问题要带上「哪个配方」，
    # 否则用户看到「配置不全」却不知道该去修哪个 —— 提示必须能照做。
    issues = []
    for row in result_rows:
        for issue in row['issues']:
            issues.append({
                'category': row['name'],
                'recipe': None,
                'code': issue['code'],
                'message': issue['message'],
                'item': issue.get('item'),
                'items': issue.get('items') or [],
                'detail': issue.get('detail'),
            })
        for recipe in row.get('recipes', []):
            for issue in recipe['issues']:
                issues.append({
                    'category': row['name'],
                    'recipe': recipe['recipe_name'],
                    'code': issue['code'],
                    'message': issue['message'],
                    'item': issue.get('item'),
                    'items': issue.get('items') or [],
                    'detail': issue.get('detail'),
                })

    snack_days = next(
        (r['snack_days'] for r in result_rows if r.get('snack_days') is not None), None,
    )

    return {
        'available': True,
        'reason': None,
        'as_of': str(today),
        'categories': result_rows,
        'shortest_category': shortest_name,
        'shortest_days': shortest_days,
        'overall': {
            'days': overall_days,
            **calc.pert_triple(overall_days),
        },
        'cash': {
            'months': cash_months,
            'days': cash_days,
            'basis': cash_basis,
        },
        'bottleneck': bottleneck,
        'bottleneck_label': SURVIVAL_BOTTLENECK_LABELS.get(bottleneck, ''),
        'coverage': coverage,
        'issues': issues,
        'snack_days': snack_days,
        'has_any_item': any(r['item_count'] for r in result_rows),
        # 必需品缺口对账（v3.59.7）—— 与生存天数**并列的第二把尺子**：
        # 天数回答「够撑多久」，对账回答「漏了什么」。两者刻意不互相代入。
        'essentials': essentials,
    }


def _cash_months() -> tuple[float | None, str]:
    """「钱能撑多久」的分子 —— **复用**应急金月数的三点估算口径

    走的路径与资产健康指标卡、比率面板完全相同（现金类资产 ÷ 近 12 月
    PERT 月支出），所以三个地方永远说同一个数。
    """
    from .cashflow_service import get_cashflow_overview

    try:
        overview = get_cashflow_overview()
    except OperationalError:
        return None, '资产快照表尚未建立'
    if not overview:
        return None, '还没有资产盘点快照，钱能撑多久暂不可算'
    months = overview.get('health_metrics', {}).get('emergency_fund_months')
    if months is None:
        return None, '月支出基准算不出来，应急金月数暂不可算'
    return float(months), '应急金月数（现金类资产 ÷ 近 12 月支出的三点估算）× 30 天'


def _redemption_window() -> tuple[date | None, date | None]:
    """三年赎回期窗口 —— 只读复用，本模块不另存一份"""
    from apps.redemption.models import RedemptionPeriod

    try:
        period = RedemptionPeriod.objects.first()
    except OperationalError:
        return None, None
    if not period:
        return None, None
    return period.start_date, period.end_date


# ──────────────────────────────────────────────────────────────
# 默认类别种子（幂等）
# ──────────────────────────────────────────────────────────────

def seed_survival_defaults(overwrite: bool = False) -> dict:
    """初始化默认类别、常用单位，以及必需品基准清单（**不预设任何物品与库存**）

    只给类别与单位的理由是：`consume_mode` 与 `aggregate_mode` 决定算法走向，
    让用户从空下拉框里猜「聚合口径」是什么意思不合理。
    必需品基准清单同理 —— 它给的是**名字与归属**（该有什么），不是数量。
    物品与库存是用户自己的数据，绝不代猜。

    幂等：同名类别 / 同名基准项已存在则跳过（overwrite=True 才覆盖）。

    ⚠️ 基准清单**必须在类别建好之后**再写 —— 种子里的类别是按名字查的，
       顺序反了会让整份清单因为「找不到归属类别」而全部跳过，
       而失败长相只是 `created_essentials: 0`，看着像「本来就没事可做」。
    """
    created_categories, created_units, updated = 0, 0, 0
    for index, seed in enumerate(SURVIVAL_CATEGORY_SEEDS):
        units = seed['units']
        category, is_new = SurvivalCategory.objects.get_or_create(
            user_id=1, name=seed['name'],
            defaults={
                'consume_mode': seed['consume_mode'],
                'aggregate_mode': seed['aggregate_mode'],
                'icon': seed['icon'],
                'description': seed['description'],
                'sort_order': index,
            },
        )
        if is_new:
            created_categories += 1
        elif overwrite:
            category.consume_mode = seed['consume_mode']
            category.aggregate_mode = seed['aggregate_mode']
            category.icon = seed['icon']
            category.description = seed['description']
            category.sort_order = index
            category.save()
            updated += 1

        for unit_index, (name, base_unit, rate, is_serving) in enumerate(units):
            _, unit_new = SurvivalUnit.objects.get_or_create(
                user_id=1, category=category, name=name,
                defaults={
                    'base_unit': base_unit,
                    'to_base_rate': rate,
                    'is_serving_unit': is_serving,
                    'sort_order': unit_index,
                },
            )
            if unit_new:
                created_units += 1

    # 必需品基准清单（v3.59.7）—— 延迟导入：本模块被包级 `__init__` 先加载，
    # 顶层互相 import 会把 `services` 包变成半初始化状态。
    from .survival_essential_service import seed_essentials

    essentials = seed_essentials(overwrite=overwrite)

    return {
        'created_categories': created_categories,
        'created_units': created_units,
        'updated_categories': updated,
        'categories': get_category_list(include_units=True),
        'essentials': essentials,
    }


# ──────────────────────────────────────────────────────────────
# 供前端直接使用的辅助信息
# ──────────────────────────────────────────────────────────────

def get_meta() -> dict:
    """口径与枚举的单一出口 —— 前端不硬编码任何文案或选项"""
    return {
        'metric_meta': calc.build_metric_meta(),
        'consume_modes': [
            {'value': v, 'label': l} for v, l in SurvivalCategory._meta.get_field('consume_mode').choices
        ],
        'aggregate_modes': [
            {'value': v, 'label': l} for v, l in SurvivalCategory._meta.get_field('aggregate_mode').choices
        ],
        'satiety': [
            {'value': v, 'label': l} for v, l in SurvivalItem._meta.get_field('satiety').choices
        ],
        'satiety_counted': list(SURVIVAL_SATIETY_COUNTED),
        'grades': [{'value': v, 'label': l} for v, l in SurvivalItem._meta.get_field('grade').choices],
        'statuses': [{'value': v, 'label': l} for v, l in SurvivalItem._meta.get_field('status').choices],
        'priorities': [
            {'value': v, 'label': l} for v, l in SurvivalItem._meta.get_field('priority').choices
        ],
        'roles': [
            {'value': v, 'label': l} for v, l in SurvivalRecipeLine._meta.get_field('role').choices
        ],
        # 按次计量的周期单位（天 / 周 / 月）—— 前端下拉直接用，不另写一份
        'use_cycle_units': [
            {'value': v, 'label': l} for v, l in SURVIVAL_USE_CYCLE_CHOICES
        ],
        'scenarios': list(calc.SURVIVAL_SCENARIOS),
        'meal_scenarios': dict(SURVIVAL_MEAL_SCENARIOS),
        'days_per_year': SURVIVAL_DAYS_PER_YEAR,
        'bottleneck_tolerance': SURVIVAL_BOTTLENECK_TOLERANCE,
        # 必需品基准清单（v3.59.7）
        'essential_scopes': [
            {'value': v, 'label': l}
            for v, l in SurvivalEssential._meta.get_field('scope').choices
        ],
        # ⚠️ 只下发**标签**，不下发分档阈值（`SURVIVAL_ESSENTIAL_LEVEL_FLOORS`）：
        #    阈值一旦到了前端，就一定会有人拿它重算一遍分档 ——
        #    那就是第二份口径，而且两边不一致时谁都不会发现。
        #    分档由后端算好放在每行的 `level` 里，前端只负责上色。
        'essential_levels': [
            {'value': value, 'label': label}
            for value, label, _ in SURVIVAL_ESSENTIAL_LEVELS
        ],
        # 衣物可穿次数参考（v3.59.8）—— 只在录入弹窗里当锚点。
        # 🔴 刻意**不进算法**：它是「别人一般填多少」，不是这件物品的参数。
        #    混进计算就等于给所有衣物套一个统一寿命 —— 那恰恰是本次要修的错
        #    （「还能穿多久」取决于接受标准，不是一个可以统一规定的数）。
        'wear_reference': [dict(row) for row in SURVIVAL_WEAR_REFERENCE],
    }
