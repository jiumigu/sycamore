"""生存资源盘点 · 必需品基准清单（v3.59.7）

这一层回答的是一个原算法**答不了**的问题：**我漏了什么。**

原状有两个洞，都在「用」类上（推导见 `constants.SURVIVAL_ESSENTIAL_SEEDS` 上方）：

    ① 「用」类的聚合口径是**求和** —— 一件囤得多的东西（洗脸巾折算 4.5 万天）
       就能把整类撑到 4.5 万天，短板永远不落在它身上，而牙膏其实只剩 5 天。
       修法在类别上：`aggregate_mode` 改成 `min`（v3.59.7 已改种子，存量需手动改）。
    ② **没录入 ≠ 不缺** —— 牙膏从来没进过系统，公式里就没有它这一项，
       于是它不构成缺口。系统只会回答「你录的东西里最少的是哪个」。

① 改一个字段就够；② 需要一把尺子 —— 就是本表。

⚠️ 与「物品」的分工（别把两件事做成一件事）：

    基准项 = 「一个人生活本该有什么」  用户视角，可增删改，**不含数量**
    物品   = 「我实际有多少」          库存事实，由消耗与盘点驱动

    两者靠 `SurvivalEssential.items`（多对多）对上：挂上了就算天数并分档，
    一件都没挂就是缺口。⚠️ 组内多件**并列取最小**，不求和 —— 判据在
    `calc.compute_essential` 的 docstring 里（睡衣分夏/秋/冬那一节）。

⚠️ 与「实盘盘点」也不同：盘点核的是**物品的数量**对不对，
   对账核的是**该有的东西在不在**。前者问「账实相符吗」，后者问「漏没漏」。
"""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from ..constants import SURVIVAL_ESSENTIAL_SEEDS
from ..models import SurvivalCategory, SurvivalEssential, SurvivalItem
from . import survival_calc as calc


def _today(reference: date | None = None) -> date:
    return reference or timezone.localdate()


def _category(category_id) -> SurvivalCategory:
    category = SurvivalCategory.objects.filter(id=category_id, user_id=1).first()
    if category is None:
        raise ValueError('归属类别不存在')
    return category


def _items(item_ids) -> list[SurvivalItem]:
    """解析关联物品列表；空值一律丢弃，重复项收敛成一件（v3.59.12）

    ⚠️ 前端可能送 `0` / `''` / `'null'` 表示「不关联」——
       直接把空串塞进多对多会在落库时炸成 500，而界面上只剩一句「保存失败」。

    ⚠️ 去重在这里做：中间表上本来就有一条 UNIQUE(survivalessential_id,
       survivalitem_id)，重复的 id 会以 `IntegrityError` 崩在事务里 ——
       而那个报错在界面上只会显示成一句兜底的「保存失败」，
       看不出是「你把同一件挂了两遍」。提前收敛掉，别让它走到 DB。

    ⚠️ 返回顺序保持用户提交的顺序：**不**按 id 排 ——
       展示顺序最终由天数决定（`compute_essential` 会重排），
       但这一层没有理由替用户重排他刚勾的那几件。
    """
    if item_ids in (None, '', 0, '0'):
        return []
    if not isinstance(item_ids, (list, tuple, set)):
        item_ids = [item_ids]

    wanted: list[int] = []
    for raw in item_ids:
        if raw in (None, '', 0, '0'):
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError('关联的物品不存在') from None
        if value not in wanted:
            wanted.append(value)
    if not wanted:
        return []

    found = {
        item.id: item
        for item in SurvivalItem.objects.filter(id__in=wanted, user_id=1)
    }
    if any(value not in found for value in wanted):
        raise ValueError('关联的物品不存在')
    return [found[value] for value in wanted]


def _assert_items_unclaimed(items: list[SurvivalItem], exclude_pk) -> None:
    """一件物品只能挂在**一处**（v3.59.13）

    用户要的是「待关联列表里不再出现已关联过的物品」；前端据此过滤候选。
    但那只是**界面** ———— 后端不拒的话，同一个物品仍能挂到第二条基准项上，
    结果是「界面看着干净、数据里是重复的」，两边还会算出两个不一样的缺口。

    ⚠️ 与序列化器里那段**故意判两遍**：序列化器挡 HTTP 面，这里挡
       脚本 / 种子 / 别的服务调用方。只留一处，绕过 HTTP 的调用会静默写坏。

    ⚠️ `exclude_pk` 传的是**自己**的主键：本行已勾选的必须留着 ——
       不留就永远摘不掉（不在候选里的东西选不掉）。
    """
    ids = [item.id for item in items]
    if not ids:
        return
    taken = dict(
        SurvivalEssential.objects
        .filter(items__id__in=ids)
        .exclude(pk=exclude_pk)
        .values_list('items__id', 'name')
    )
    if not taken:
        return
    labels = {item.id: item.name for item in items}
    detail = '；'.join(
        f'「{labels.get(i, i)}」已挂在「{taken[i]}」下' for i in ids if i in taken
    )
    raise ValueError(
        f'一件物品只能挂在一处：{detail}。要从那一条上摘掉，'
        f'或者确认这件东西真的只属于这里。',
    )


# ──────────────────────────────────────────────────────────────
# 读
# ──────────────────────────────────────────────────────────────

def get_essential_list(
    category_id: int | None = None,
    scope: str | None = None,
    sort_by_urgency: bool = True,
) -> list[dict]:
    """基准清单 + 逐项对账结果

    ⚠️ 默认按**紧迫度**排（该先处理的在前），不是按名字 ——
       一张按名字排的对账表等于把最要紧的那件藏进中间几行。
       传入 `sort_by_urgency=False` 可得录入顺序（管理界面用得上）。
    """
    qs = (
        SurvivalEssential.objects
        .filter(user_id=1)
        .select_related('category')
        .prefetch_related('items__unit')
        .order_by('sort_order', 'id')
    )
    if category_id:
        qs = qs.filter(category_id=category_id)
    if scope:
        qs = qs.filter(scope=scope)

    today = _today()
    rows = [calc.compute_essential(essential, today) for essential in qs]
    if sort_by_urgency:
        rows.sort(key=calc.essential_sort_key)
    return rows


def get_reconcile(reference_date: date | None = None) -> dict:
    """缺口对账（汇总 + 最短的一件）—— 供综合分析内联使用

    ⚠️ 刻意**不把明细塞进综合分析**：总览只要「缺了几件、最短的是哪件」，
       明细由 `/survival/essentials/` 单独提供。两处都塞全量明细，
       将来必然出现「总览的数和列表的数不一样」——因为其中一处忘了同步取数条件。
    """
    today = _today(reference_date)
    qs = (
        SurvivalEssential.objects
        .filter(user_id=1)
        .select_related('category')
        .prefetch_related('items__unit')
        .order_by('sort_order', 'id')
    )
    rows = [calc.compute_essential(essential, today) for essential in qs]
    return {
        'summary': calc.summarize_essentials(rows),
        'shortest': calc.find_essential_shortest(rows),
        'is_configured': bool(rows),
    }


# ──────────────────────────────────────────────────────────────
# 写
# ──────────────────────────────────────────────────────────────

def create_essential(payload: dict) -> dict:
    data = dict(payload)
    category = _category(data.pop('category_id'))
    items = _items(data.pop('item_ids', None))
    _assert_items_unclaimed(items, None)
    essential = SurvivalEssential.objects.create(
        user_id=1, category=category, **data,
    )
    if items:
        essential.items.set(items)
    return calc.compute_essential(essential, _today())


def update_essential(pk: int, payload: dict) -> dict:
    essential = SurvivalEssential.objects.get(id=pk, user_id=1)
    data = dict(payload)
    if 'category_id' in data:
        essential.category = _category(data.pop('category_id'))
    if 'item_ids' in data:
        # ⚠️ 空列表 = **清空关联**，与「没传这个字段」是两件事：
        #    前者是用户把勾选全取消了，后者是这次提交不打算动它。
        #    `set([])` 恰好表达前者，而 `if` 判空会让它变成后者 ——
        #    那样用户取消勾选后点保存，界面看着清空了、刷新又回来。
        resolved = _items(data.pop('item_ids'))
        _assert_items_unclaimed(resolved, essential.pk)
        essential.items.set(resolved)
    for key, value in data.items():
        setattr(essential, key, value)
    essential.save()
    return calc.compute_essential(essential, _today())


def delete_essential(pk: int) -> int:
    """删除一件基准项

    ⚠️ 与「删物品」的处置**刻意不同**：删基准项只影响这把尺子，
       不碰任何库存 —— 关联的物品是用户的资产，不该因为少了一条认知就消失。
       所以这里不需要「先解除引用」那一步（对比 `delete_item`）。
    """
    essential = SurvivalEssential.objects.get(id=pk, user_id=1)
    essential.delete()
    return pk


# ──────────────────────────────────────────────────────────────
# 基准清单种子（幂等）
# ──────────────────────────────────────────────────────────────

@transaction.atomic
def seed_essentials(overwrite: bool = False) -> dict:
    """写入必需品基准清单（幂等）

    ⚠️ 同名已存在**默认跳过**：用户可能改过它的性质、或已经关联了物品 ——
       静默覆盖会把这些改动抹掉，而用户只会发现「我上次改的东西又变回去了」。
       要覆盖须显式 `overwrite=True`。

    ⚠️ 种子里的类别写的是**名字**，要按名找回类别；找不到就跳过并计数 ——
       凭空建一个类别会绕过「不预设用户的分类结构」那条判据。
       （「医药」类别还没初始化时，医药类必需品的处理方式就是跳过。）

    整段放进一个事务：中途失败留下半份清单，用户看到的是一份
    「有的有、有的没有」的尺子，比完全没有更容易误导。
    """
    created, updated, skipped = 0, 0, 0
    missing_categories: list[str] = []

    for index, (category_name, name, scope, unit_name, hint) in enumerate(
        SURVIVAL_ESSENTIAL_SEEDS,
    ):
        category = SurvivalCategory.objects.filter(user_id=1, name=category_name).first()
        if category is None:
            skipped += 1
            if category_name not in missing_categories:
                missing_categories.append(category_name)
            continue

        essential, is_new = SurvivalEssential.objects.get_or_create(
            user_id=1,
            name=name,
            defaults={
                'category': category,
                'scope': scope,
                'unit_name': unit_name,
                'hint': hint,
                'sort_order': index,
            },
        )
        if is_new:
            created += 1
        elif overwrite:
            essential.category = category
            essential.scope = scope
            essential.unit_name = unit_name
            essential.hint = hint
            essential.sort_order = index
            essential.save()
            updated += 1
        else:
            skipped += 1

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'seeded_total': len(SURVIVAL_ESSENTIAL_SEEDS),
        'missing_categories': missing_categories,
    }
