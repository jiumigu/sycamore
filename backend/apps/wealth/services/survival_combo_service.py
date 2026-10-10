"""生存资源 · 组合（v3.59.13）

    「燕麦米、绿豆、薏仁、紫米是**分开登记**的，但烹饪时**一起下锅**。」

登记与「一起用」是两件事，本模块只管后者。三条口径写在这里，也写在模型注释里：

一、组合 = 有哪几件 + 每餐各用多少 + 叫什么，**不放餐位**
    同一锅杂粮粥在早餐配方里可能是必配位、在别的场景可能是主食位 ——
    餐位是**配方行的属性**，锁死在组合上就表达不了。

二、组内取最小（并列缺一不可）—— 四样都要下锅，能煮几顿看最先耗尽的那件
    计算在 `survival_calc.compute_combo_line`，本模块一个除法都不做。
    服务层只负责「取数 + 校验 + 组装」，口径分散两处迟早不一致。

三、组合里**没有「份数」倍率**
    「倍数 × 另一处用量」是本项目踩过的形状：两个数各自看着正常，
    乘起来才错，界面上看不出来（「一份能用几次」× 数量 = 45,000 天那次）。
    要加量请改成员那一行的「每餐用量」—— 用量的唯一落点在成员上。

⚠️ 组合与物品的**类别必须一致**（含成员与用量单位）：跨类别的组合意味着
   「吃」的配方引用了「用」类的物品，而那正是配方行既有校验要拦的事 ——
   两边判据必须一样，否则会出现「配方不让混、组合让混」的漏洞。
"""

from __future__ import annotations

from django.db import transaction

from ..models import SurvivalCategory, SurvivalCombo, SurvivalComboItem, SurvivalItem, SurvivalUnit


def _category(category_id) -> SurvivalCategory:
    category = SurvivalCategory.objects.filter(id=category_id, user_id=1).first()
    if category is None:
        raise ValueError('归属类别不存在')
    return category


def _resolve_item(value) -> SurvivalItem:
    try:
        item_id = int(value)
    except (TypeError, ValueError):
        raise ValueError('组合里的物品不存在') from None
    item = SurvivalItem.objects.filter(id=item_id, user_id=1).first()
    if item is None:
        raise ValueError('组合里的物品不存在')
    return item


def _resolve_unit(value, category: SurvivalCategory) -> SurvivalUnit | None:
    """用量单位可留空 = 跟随物品自己的单位（与配方行同源）"""
    if value in (None, '', 0, '0'):
        return None
    try:
        unit_id = int(value)
    except (TypeError, ValueError):
        raise ValueError('用量单位不存在') from None
    unit = SurvivalUnit.objects.filter(id=unit_id, user_id=1).first()
    if unit is None:
        raise ValueError('用量单位不存在')
    if unit.category_id != category.id:
        raise ValueError(f'单位「{unit.name}」不属于「{category.name}」类别')
    return unit


def _members(entries, category: SurvivalCategory) -> list[dict]:
    """把入参里的成员列表收敛成可以直接落库的一组

    🔴 四道校验都在这里做，一条都不能省：

        ① **空列表直接拒绝** —— 零件的组合会让配方里那一行变成「无约束」，
           而界面上看着像配好了（同 `empty_combo` 那条问题码）。
        ② **去重**：`UNIQUE(combo, item)` 是 DB 层的，DRF 与调用方都不保证，
           重复 id 会以 `IntegrityError` 崩在事务里，界面只显示「保存失败」——
           看不出是「同一件挂了两遍」。而且重复本身就是**隐性倍率**。
        ③ **同类别**：跨类别成员会让「吃」的组合里混进「用」类物品。
        ④ **用量 > 0**：0 或负数会让「能煮几顿」变成无穷大或负数。
    """
    if entries in (None, ''):
        raise ValueError('组合至少要有一件物品')
    if not isinstance(entries, (list, tuple)):
        raise ValueError('组合成员格式不对')

    resolved: list[dict] = []
    seen: set[int] = set()
    for raw in entries:
        if not isinstance(raw, dict):
            raise ValueError('组合成员格式不对')
        item = _resolve_item(raw.get('item_id'))
        if item.id in seen:
            raise ValueError(f'「{item.name}」在同一个组合里出现了两次；加量请改它的每餐用量')
        seen.add(item.id)
        if item.category_id != category.id:
            raise ValueError(
                f'「{item.name}」不属于「{category.name}」类别，'
                f'组合里的物品必须与组合同属一个类别',
            )
        try:
            quantity = float(raw.get('quantity_per_serving'))
        except (TypeError, ValueError):
            raise ValueError(f'「{item.name}」的每餐用量必须是数字') from None
        if quantity <= 0:
            raise ValueError(f'「{item.name}」的每餐用量必须大于零')
        resolved.append({
            'item': item,
            'quantity_per_serving': quantity,
            'unit': _resolve_unit(raw.get('unit_id'), category),
        })

    if not resolved:
        raise ValueError('组合至少要有一件物品')
    return resolved


# ──────────────────────────────────────────────────────────────
# 读
# ──────────────────────────────────────────────────────────────

def _member_row(member: SurvivalComboItem) -> dict:
    item = member.item
    return {
        'item_id': item.id,
        'item_name': item.name,
        'quantity_per_serving': float(member.quantity_per_serving),
        'unit_id': member.unit_id,
        'unit_name': member.unit.name if member.unit else '',
        'item_unit_name': item.unit.name if item.unit else '',
        'stock': float(item.quantity),
        'stock_unit_name': item.unit.name if item.unit else '',
    }


def _combo_row(combo: SurvivalCombo, with_members: bool = True) -> dict:
    members = list(combo.members.select_related('item', 'item__unit', 'unit').order_by('id'))
    row = {
        'id': combo.id,
        'category_id': combo.category_id,
        'category_name': combo.category.name,
        'name': combo.name,
        'note': combo.note,
        'sort_order': combo.sort_order,
        'member_count': len(members),
        # 被几个配方引用 —— 界面要能**在点删除之前**看见：
        # 被引用的组合删不掉，不提前显示就等于让人白点一次。
        'recipe_ref_count': combo.recipe_lines.count(),
    }
    if with_members:
        row['members'] = [_member_row(member) for member in members]
    return row


def get_combo_list(category_id: int | None = None, with_members: bool = True) -> list[dict]:
    qs = SurvivalCombo.objects.filter(user_id=1).select_related('category')
    if category_id:
        qs = qs.filter(category_id=category_id)
    return [
        _combo_row(combo, with_members=with_members)
        for combo in qs.order_by('category_id', 'sort_order', 'id')
    ]


# ──────────────────────────────────────────────────────────────
# 写
# ──────────────────────────────────────────────────────────────

@transaction.atomic
def create_combo(payload: dict) -> dict:
    """新建组合（含成员）。

    整体放进一个事务：组合建好了但成员没建，会得到一个「0 件」的组合，
    它会让配方里那一行**变成无约束**却看着像配好了。
    """
    data = dict(payload)
    category = _category(data.pop('category_id'))
    members = _members(data.pop('members', None), category)
    combo = SurvivalCombo.objects.create(user_id=1, category=category, **data)
    _replace_members(combo, members)
    return _combo_row(combo)


@transaction.atomic
def update_combo(pk: int, payload: dict) -> dict:
    """更新组合 —— 成员**全删重建**（与配方行同源：逐行 diff 换不来什么）

    ⚠️ 改了组合会**同时影响所有引用它的配方**（可复用实体的代价，也是它的收益）。
       界面必须提前说清这一点，否则「我只改了自己的组合」与
       「顺便改了三个配方」看起来是同一件事。
    """
    combo = SurvivalCombo.objects.get(id=pk, user_id=1)
    data = dict(payload)
    if 'category_id' in data:
        combo.category = _category(data.pop('category_id'))
    members = data.pop('members', None)
    for key, value in data.items():
        setattr(combo, key, value)
    combo.save()
    if members is not None:
        _replace_members(combo, _members(members, combo.category))
    return _combo_row(combo)


def _replace_members(combo: SurvivalCombo, members: list[dict]) -> None:
    combo.members.all().delete()
    for raw in members:
        SurvivalComboItem.objects.create(combo=combo, **raw)


def delete_combo(pk: int) -> int:
    """删除组合 —— **被配方引用时拒绝**，先让用户把引用摘掉

    ⚠️ 与「删基准项」刻意不同（那边不需解除引用，因为基准项不参与分母）。
       组合是配方行的**计量来源**：删掉它，那一行就没有用量了，
       整道菜会因此算不出来或算得更耐吃。宁可报错也不做这种魔法。
    """
    combo = SurvivalCombo.objects.get(id=pk, user_id=1)
    used = combo.recipe_lines.count()
    if used:
        raise ValueError(
            f'组合「{combo.name}」还被 {used} 个配方引用，不能直接删除；'
            f'请先从配方里移除它。',
        )
    combo.delete()
    return pk
