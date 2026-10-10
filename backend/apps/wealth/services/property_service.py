"""物件资产 · 服务层（取数与组装）

只做三件事：取数、组装、CRUD 编排。
**一个除法都不在这里做** —— 全部派生值来自 `property_calc`（唯一真源），
视图层只做协议转换，前端只把数摆出来。

命名提醒：`services/__init__` 是一个**扁平命名空间**，
`get_category_list` / `create_category` 这些词已被 survival_service 占用，
故本模块的函数在包级导出时一律加 `property` 限定（`services/__init__.py` 里用 `as` 别名）；
模块内部仍用短名 —— 这里有两层模块名限定，不会歧义。
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from ..constants import (
    PROPERTY_CATEGORY_SEEDS,
    PROPERTY_CONDITION_CHOICES,
    PROPERTY_ISSUE_LABELS,
    PROPERTY_STATUS_CHOICES,
    PROPERTY_STATUS_SCRAPPED,
)
from ..models import WealthProperty, WealthPropertyCategory
from . import property_calc as calc


def _today(reference: date | None = None) -> date:
    return reference or date.today()


# ──────────────────────────────────────────────────────────────
# 类别（轻量主数据）
# ──────────────────────────────────────────────────────────────

def _category_row(category: WealthPropertyCategory) -> dict:
    return {
        'id': category.id,
        'name': category.name,
        'icon': category.icon,
        'default_lifespan_months': category.default_lifespan_months,
        'sort_order': category.sort_order,
        'note': category.note,
        # 让「类别维护」页能一眼看出哪些类别还在被用 ——
        # 也解释了为什么删不掉（有引用就是 400）。
        'property_count': category.properties.count(),
    }


def get_category_list() -> list[dict]:
    qs = WealthPropertyCategory.objects.filter(user_id=1).order_by('sort_order', 'id')
    return [_category_row(c) for c in qs]


def _resolve_category(category_id) -> WealthPropertyCategory:
    """按 id 取类别；取不到直接抛 —— 让请求 400，而不是静默挂到一个错的类别上。"""
    if category_id is None:
        raise ValueError('必须指定类别')
    category = WealthPropertyCategory.objects.filter(id=category_id, user_id=1).first()
    if category is None:
        raise ValueError(f'类别 {category_id} 不存在')
    return category


def _assert_name_available(name: str, exclude_pk=None) -> str:
    name = (name or '').strip()
    if not name:
        raise ValueError('类别名称不能为空')
    qs = WealthPropertyCategory.objects.filter(user_id=1, name=name)
    if exclude_pk is not None:
        qs = qs.exclude(id=exclude_pk)
    if qs.exists():
        raise ValueError(f'已存在名为「{name}」的类别')
    return name


def create_category(payload: dict) -> dict:
    category = WealthPropertyCategory.objects.create(
        user_id=1,
        name=_assert_name_available(payload.get('name')),
        icon=payload.get('icon') or '',
        default_lifespan_months=payload.get('default_lifespan_months'),
        note=payload.get('note') or '',
        sort_order=payload.get('sort_order') or 0,
    )
    return _category_row(category)


def update_category(pk: int, payload: dict) -> dict:
    category = WealthPropertyCategory.objects.get(id=pk, user_id=1)
    if 'name' in payload:
        category.name = _assert_name_available(payload['name'], exclude_pk=pk)
    if 'icon' in payload:
        category.icon = payload['icon'] or ''
    if 'note' in payload:
        category.note = payload['note'] or ''
    # 默认年限是**可清空的**（用户可以把预填值撤掉）—— 所以不能写 `if value is not None`
    if 'default_lifespan_months' in payload:
        category.default_lifespan_months = payload['default_lifespan_months']
    if 'sort_order' in payload and payload['sort_order'] is not None:
        category.sort_order = payload['sort_order']
    category.save()
    return _category_row(category)


def delete_category(pk: int) -> int:
    """删除类别 —— **先看里面有没有物件**，不级联

    级联删除会让「删掉一个建错的空类别」与「删掉整柜家当」走同一个按钮，
    代价完全不对称、且不可逆。这里宁可多一步，并把数量报出来让人能照做。
    """
    category = WealthPropertyCategory.objects.get(id=pk, user_id=1)
    count = category.properties.count()
    if count:
        raise ValueError(
            f'「{category.name}」下还有 {count} 件物件，不能直接删除；'
            f'请先把这些物件改到别的类别，或逐件删除。',
        )
    category.delete()
    return pk


def seed_property_categories(overwrite: bool = False) -> dict:
    """初始化默认类别（幂等）—— **只建类别，不预设任何物件**

    只给类别这六个值的理由：它们是「用途」这把尺子的常见刻度，
    让人从空下拉框开始建自己的分类太费事。物件是用户自己的数据，绝不代猜。

    🔴 种子里**没有默认使用年限**（`default_lifespan_months` 留空）——
       那是用户自己的判断。给一个「空调 10 年」的通用值等于系统替他定了这件事，
       而预填的正确语义是「执行用户自己的意志」（详见 constants 里的注释）。

    幂等：同名类别已存在则跳过（`overwrite=True` 才覆盖图标与说明）。
    """
    created, updated, skipped = 0, 0, 0
    for index, seed in enumerate(PROPERTY_CATEGORY_SEEDS):
        defaults = {
            'icon': seed.get('icon', ''),
            'note': seed.get('note', ''),
            'sort_order': index,
        }
        category, is_new = WealthPropertyCategory.objects.get_or_create(
            user_id=1, name=seed['name'], defaults=defaults,
        )
        if is_new:
            created += 1
        elif overwrite:
            for key, value in defaults.items():
                setattr(category, key, value)
            category.save()
            updated += 1
        else:
            skipped += 1
    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'categories': get_category_list(),
    }


# ──────────────────────────────────────────────────────────────
# 物件
# ──────────────────────────────────────────────────────────────

def _item_row(prop, today: date | None = None) -> dict:
    """一件物件的完整行 —— 原始字段 + 全部派生值。

    派生值**一个都不在这里算**，全部来自 `property_calc.compute_property`。
    """
    computed = calc.compute_property(prop, today=today)
    return {
        'id': prop.id,
        'name': prop.name,
        'spec': prop.spec,
        'location': prop.location,
        'category_id': prop.category_id,
        'category_name': prop.category.name if prop.category is not None else '',
        'purchase_amount': prop.purchase_amount,
        'purchase_date': prop.purchase_date,
        'lifespan_months': prop.lifespan_months,
        'status': prop.status,
        'condition': prop.condition,
        'scrapped_date': prop.scrapped_date,
        'dispose_note': prop.dispose_note,
        'note': prop.note,
        'tags': prop.tags,
        'created_at': prop.created_at,
        'updated_at': prop.updated_at,
        **computed,
    }


def get_item_list(
    category_id=None,
    status=None,
    condition=None,
    search=None,
    reference: date | None = None,
) -> list[dict]:
    """物件列表 —— 支持按类别 / 状态 / 状况 / 关键词筛选。

    ⚠️ 返回**裸数组**（视图层 `pagination_class = None`）：被 DRF 全局分页包成
       `{count, results}` 后，前端按数组消费会**静默显示为空**（项目硬坑③）。

    ⚠️ 排序交给这里（模型刻意不设 `Meta.ordering`）：最近录入的在前。
       **不提供 `?ordering=` 参数** —— 按金额排序是前端的事。一旦开到后端，
       `current_value`（派生值、不落库）会被逼着落库，撕开「派生值不落库」的口子
       （设计文档 §4.3 专条）。
    """
    qs = WealthProperty.objects.select_related('category').filter(user_id=1)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if status:
        qs = qs.filter(status=status)
    if condition:
        qs = qs.filter(condition=condition)
    if search:
        qs = qs.filter(name__icontains=search)
    qs = qs.order_by('-created_at', '-id')
    today = _today(reference)
    return [_item_row(p, today=today) for p in qs]


def get_item(pk: int, reference: date | None = None) -> dict | None:
    prop = (
        WealthProperty.objects.select_related('category')
        .filter(id=pk, user_id=1).first()
    )
    return _item_row(prop, today=_today(reference)) if prop else None


def _clear_scrap_fields_if_needed(prop: WealthProperty) -> None:
    """状态不是「已报废」时，报废日期与处置备注一律置空。

    🔴 必须由**服务端**保证，不指望客户端记得送 null ——
       漏了它就会出现「状态是在用、却带着报废日期」的自相矛盾行，
       而那种行在列表里看起来完全正常（少一个字段没人会发现）。
       这与「按次三兄弟」的置空是同一条判据。

    ⚠️ 清空是**可见的**（表单上那两个格子会空掉），不是静默改写。
    """
    if prop.status == PROPERTY_STATUS_SCRAPPED:
        return
    if prop.scrapped_date is not None or prop.dispose_note:
        prop.scrapped_date = None
        prop.dispose_note = ''
        prop.save(update_fields=['scrapped_date', 'dispose_note', 'updated_at'])


def create_item(payload: dict) -> dict:
    category = _resolve_category(payload.pop('category_id', None))
    prop = WealthProperty.objects.create(user_id=1, category=category, **payload)
    _clear_scrap_fields_if_needed(prop)
    return _item_row(prop)


def update_item(pk: int, payload: dict) -> dict:
    prop = WealthProperty.objects.get(id=pk, user_id=1)
    if 'category_id' in payload:
        prop.category = _resolve_category(payload.pop('category_id'))
    for key, value in payload.items():
        setattr(prop, key, value)
    prop.save()
    _clear_scrap_fields_if_needed(prop)
    return _item_row(prop)


def delete_item(pk: int) -> int:
    """删除一件物件 —— **物理删除**。

    本模块**没有**软删开关：报废已经承担了「不用了」的语义，
    再叠一个 `is_active` 就会出现「已报废 + 已停用」这种谁也说不清的状态。
    录错的记录直接删（界面上走确认框）。
    """
    prop = WealthProperty.objects.get(id=pk, user_id=1)
    prop.delete()
    return pk


def preview_item(payload: dict, reference: date | None = None) -> dict:
    """保存前试算 —— **不写库**，且走与保存**完全相同**的那段代码。

    🔴 四条铁律（同生存资源十一期的账）：
       ① **不写第二份公式**：这里造一个只活在内存里的对象喂给 `compute_property`，
          而不是另写一遍折旧 —— 两份公式迟早分叉，且分叉是静默的
          （试算说一个数、保存后写着另一个数，两边都像个正常的数）。
       ② 校验复用同一个表单序列化器（由视图层负责）。
       ③ 试算是**护栏、不是闸门** —— 它自己失败只降级成提示，绝不阻断保存。
       ④ 返回体与保存后那一行**同构**（都走 `_item_row`），字段不会各自漂移。

    ⚠️ 这里体现的是「保存之后会变成什么样」，所以与保存一样：
       状态不是已报废时，报废日期不参与计算。
    """
    category = _resolve_category(payload.get('category_id'))
    status = payload.get('status') or 'in_use'
    draft = SimpleNamespace(
        id=None,
        name=payload.get('name') or '',
        spec=payload.get('spec') or '',
        location=payload.get('location') or '',
        category_id=category.id,
        category=category,
        purchase_amount=payload.get('purchase_amount'),
        purchase_date=payload.get('purchase_date'),
        lifespan_months=payload.get('lifespan_months'),
        status=status,
        condition=payload.get('condition') or 'normal',
        scrapped_date=(
            payload.get('scrapped_date') if status == PROPERTY_STATUS_SCRAPPED else None
        ),
        dispose_note=(
            (payload.get('dispose_note') or '')
            if status == PROPERTY_STATUS_SCRAPPED else ''
        ),
        note=payload.get('note') or '',
        tags=payload.get('tags') or [],
        created_at=None,
        updated_at=None,
    )
    return _item_row(draft, today=_today(reference))


# ──────────────────────────────────────────────────────────────
# 汇总与元信息
# ──────────────────────────────────────────────────────────────

def get_summary(reference: date | None = None) -> dict:
    """首屏四卡 —— 在用件数 / 原值合计 / 在用净值合计 / 已报废。

    合计口径全部来自 `property_calc.summarize`（唯一真源），
    这里的职责只是**把行喂进去**，不重算任何数。
    """
    today = _today(reference)
    rows = []
    for prop in WealthProperty.objects.select_related('category').filter(user_id=1):
        computed = calc.compute_property(prop, today=today)
        rows.append({
            'status': prop.status,
            # condition 只用于数出「因损坏按 0 计」的件数（broken_count）——
            # 它**不**参与金额，别在这里顺手把它算进去。
            'condition': prop.condition,
            'purchase_amount': prop.purchase_amount,
            'current_value': computed['current_value'],
        })
    return calc.summarize(rows)


def get_meta() -> dict:
    """口径与枚举的单一出口 —— 前端不硬编码任何文案或选项"""
    return {
        'statuses': [{'value': v, 'label': l} for v, l in PROPERTY_STATUS_CHOICES],
        'conditions': [{'value': v, 'label': l} for v, l in PROPERTY_CONDITION_CHOICES],
        'metric_meta': calc.build_metric_meta(),
        'issue_labels': dict(PROPERTY_ISSUE_LABELS),
        # 页面里固定那一句说明 —— 放这里是为了它只有一个来源
        'not_in_net_worth_note': '此合计不计入净资产，仅作家当参考',
        'subtitle': '管的是物件：家电 / 家具 / 数码，不是钱',
    }
