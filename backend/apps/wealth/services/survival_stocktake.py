"""生存资源盘点 · 实盘盘点服务层

与 `survival_snapshot` 的分工（这两件事最容易被混为一谈，在这里写死）：

    survival_snapshot    系统算出来的**结论** —— 我以为能撑多久，不需要人动手
    survival_stocktake   人填进去的**实盘** —— 实际还剩多少件，必须人动手

合在一起的后果是「点一下按钮就说自己盘过了」—— 那是假盘点，而且它会把
历史记录的证据价值一并毁掉：记录还在，但它证明不了任何事。

四条铁律：

一、**账面数量由服务层在读的那一刻取，不信前端传的值。**
    盘点页面可能开着很久，期间库存已经被别处改过。信前端的数会把
    「盘点期间发生的变化」算进盘盈盘亏，差额还与实物对不上。
    这不只是防篡改 —— 前端那个数本来就可能是**陈旧**的，防的是一个必然发生的过期读。

二、**提交即校准**：库存直接改成实盘数。
    否则「我数过了」这件事只留下一张纸，账还是错的，下次还得再数一遍。

三、**删除记录不回滚库存。**
    库存已经是**被核实过的事实**，删记录只是删掉凭据。
    若删一条历史记录会把库存静默改回去，「删记录」就成了一个能改现状的按钮 ——
    而且是个看起来只影响历史的按钮。要改数量请去编辑物品，
    那是一个明确指向「改现状」的入口。

四、**delta 不落库、book_quantity 必须落库。**
    这条看着自相矛盾，其实正是「以后重算得出同样结果吗」的判据在两侧：
    账面与实盘都在表里，一减就有 ⇒ delta 不落库；
    而「盘点那一刻账上有多少」在库存被校准之后就**永久消失了**，重算不出 ⇒ 必须落库。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from ..constants import (
    SURVIVAL_STOCKTAKE_DEFAULT_LIMIT,
    SURVIVAL_STOCKTAKE_MAX_LIMIT,
    SURVIVAL_STOCKTAKE_MAX_LINES,
    SURVIVAL_STOCKTAKE_SOURCES,
)
from ..models import SurvivalItem, SurvivalStocktake, SurvivalStocktakeLine

# 🔴 库存的**唯一写口**（v3.60.18）。盘点改数量也要从这里过 ——
#    否则「库存怎么变的」在盘点这一环就断了：账被校准了，流水里却没有那一笔。
from .survival_flow import record_flow

SOURCE_LABELS = dict(SURVIVAL_STOCKTAKE_SOURCES)

DELTA_SURPLUS = 'surplus'
DELTA_DEFICIT = 'deficit'
DELTA_FLAT = 'flat'


# ══════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════

def _f(value) -> float | None:
    """Decimal / None → float / None（与 `survival_calc._f` 同口径，避免 Decimal 混进 JSON）"""
    if value is None:
        return None
    return float(value)


def _dec(value) -> Decimal | None:
    """入参转 Decimal；转不动返回 None（由调用方报 400，不在这里抛）"""
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _clamp_limit(limit) -> int:
    """limit 是「看多少」的视角参数，超界夹到边界、不报错。

    ⚠️ 上限必须存在 —— 不设上限等于让一次请求把全部历史拉出来。
       非法值回落到默认值，理由同 `survival_snapshot._clamp_limit`。
    """
    try:
        size = int(limit)
    except (TypeError, ValueError):
        return SURVIVAL_STOCKTAKE_DEFAULT_LIMIT
    if size <= 0:
        return SURVIVAL_STOCKTAKE_DEFAULT_LIMIT
    return min(size, SURVIVAL_STOCKTAKE_MAX_LIMIT)


def delta_kind(book, actual) -> str:
    """差异方向：正 = 盘盈、负 = 盘亏、零 = 核对无误

    ⚠️ 方向**只表示实物比账上多还是少**，不表示好坏：
       盘亏不一定是坏事（可能是之前多记了），盘盈也不一定是好事（可能是漏记消耗）。
       所以界面不给它套「涨红跌绿」那套价格语义 —— 那是给涨跌用的。
    """
    if actual > book:
        return DELTA_SURPLUS
    if actual < book:
        return DELTA_DEFICIT
    return DELTA_FLAT


# ══════════════════════════════════════════════════════════════
# 行组装
# ══════════════════════════════════════════════════════════════

def _line_row(line: SurvivalStocktakeLine) -> dict:
    delta = line.actual_quantity - line.book_quantity
    return {
        'id': line.id,
        'item_id': line.item_id,
        'item_name': line.item_name,
        'category_name': line.category_name,
        'unit_name': line.unit_name,
        'book_quantity': _f(line.book_quantity),
        'actual_quantity': _f(line.actual_quantity),
        'delta': _f(delta),
        'delta_kind': delta_kind(line.book_quantity, line.actual_quantity),
        'note': line.note,
    }


def _stocktake_row(head: SurvivalStocktake, with_lines: bool = True) -> dict:
    rows = [_line_row(line) for line in head.lines.all()]
    surplus = [r for r in rows if r['delta_kind'] == DELTA_SURPLUS]
    deficit = [r for r in rows if r['delta_kind'] == DELTA_DEFICIT]

    data = {
        'id': head.id,
        'stocktake_date': str(head.stocktake_date),
        'source': head.source,
        'source_label': SOURCE_LABELS.get(head.source, head.source),
        'note': head.note,
        'line_count': len(rows),
        'surplus_count': len(surplus),
        'deficit_count': len(deficit),
        'flat_count': len(rows) - len(surplus) - len(deficit),
        'created_at': head.created_at.isoformat() if head.created_at else None,
    }
    # ⚠️ 列表**带**明细，与二期快照列表「刻意不带明细」的选择相反。
    #    判据不同：快照的明细是**另一个维度**（各类别的结论），列表只要读数就够；
    #    而盘点的明细**就是内容本身** —— 只给汇总（「盘了 12 项、3 盈 2 亏」），
    #    用户还得再点一次才知道是哪三件，等于把唯一的答案藏起来。
    #    规模也可控：一次实盘通常几十行。
    if with_lines:
        data['lines'] = rows
    return data


# ══════════════════════════════════════════════════════════════
# 读：盘点工作表
# ══════════════════════════════════════════════════════════════

def _last_stocktake_map(item_ids: list[int]) -> dict[int, date]:
    """每件物品**最近一次被盘到**的日期（从未盘过的不在表里）

    ⚠️ `SurvivalStocktakeLine` 没有 user_id，归属要经 `stocktake__user_id` 走 ——
       别顺手给它加一个 user_id 字段，那会与快照明细的「明细不带 user、靠头归属」
       不一致，而两张表是同一套设计。
    """
    if not item_ids:
        return {}
    rows = (
        SurvivalStocktakeLine.objects
        .filter(stocktake__user_id=1, item_id__in=item_ids)
        .values('item_id')
        .annotate(last=Max('stocktake__stocktake_date'))
        # 显式清序：managed 表本身没有 Meta.ordering，这里是**防御性**的 ——
        # 一旦将来有人给模型加上 ordering，聚合会被静默注入（项目硬坑②）。
        .order_by()
    )
    return {r['item_id']: r['last'] for r in rows if r['item_id'] is not None}


def get_worksheet(
    category_id: int | None = None,
    item_ids: list[int] | None = None,
    keyword: str | None = None,
) -> list[dict]:
    """盘点工作表：待盘物品 + 当前账面 + 上次盘点

    这是「盘点单的模板」：用户勾哪些，就往哪些上面填实盘数。

    ⚠️ 这里下发的 `book_quantity` **只用于界面显示**（让用户知道系统记的是多少），
       提交时**不作数** —— 服务端会重新读一次。见模块头的铁律一。
    """
    qs = SurvivalItem.objects.filter(user_id=1).select_related('category', 'unit')
    if category_id:
        qs = qs.filter(category_id=category_id)
    if item_ids:
        qs = qs.filter(id__in=item_ids)
    if keyword:
        qs = qs.filter(name__icontains=keyword)

    items = list(qs.order_by('category_id', 'name'))
    last_map = _last_stocktake_map([i.id for i in items])
    today = timezone.localdate()

    rows: list[dict] = []
    for item in items:
        last = last_map.get(item.id)
        gap = (today - last).days if last else None
        cycle = item.stocktake_cycle_days
        threshold = item.restock_threshold
        rows.append({
            'item_id': item.id,
            'name': item.name,
            'category_id': item.category_id,
            'category_name': item.category.name,
            'unit_name': item.unit.name if item.unit else '',
            'book_quantity': _f(item.quantity),
            'status': item.status,
            'expire_date': str(item.expire_date) if item.expire_date else None,
            'last_stocktake_date': str(last) if last else None,
            'days_since_stocktake': gap,
            'stocktake_cycle_days': cycle,
            # ⚠️ 「该盘了」只在**设了周期**时才判。
            #    若把「从未盘过」也算作该盘，那所有没设周期的物品会一律标红 ——
            #    等于没有标，用户很快就学会无视这个标记。
            'stocktake_due': bool(cycle) and (gap is None or gap >= cycle),
            'restock_threshold': _f(threshold),
            # 判据用「降到阈值」而不是「低于阈值」：阈值是触发线，
            # 到了就该补。写成严格小于会让「正好剩 2 包、阈值 2」不提醒。
            'below_threshold': (
                threshold is not None and item.quantity <= threshold
            ),
        })
    return rows


# ══════════════════════════════════════════════════════════════
# 写：提交盘点
# ══════════════════════════════════════════════════════════════

def _normalize_lines(lines) -> list[dict]:
    """校验并归一化入参；任何一处不合规都抛 ValueError（视图转 400）

    ⚠️ 同一件物品在一张单里出现两次必须报错，不能「后一条覆盖前一条」：
       那会让库存被改写成后填的那个数，而前一条实盘数**已经在页面上显示过**了。
    """
    if not lines:
        raise ValueError('这次盘点一件物品都没有填，先勾几件再提交。')
    if len(lines) > SURVIVAL_STOCKTAKE_MAX_LINES:
        raise ValueError(
            f'一次最多提交 {SURVIVAL_STOCKTAKE_MAX_LINES} 行，本次 {len(lines)} 行。'
            f'请分批盘点。',
        )

    out: list[dict] = []
    seen: set[int] = set()
    for raw in lines:
        item_id = raw.get('item_id')
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            raise ValueError('盘点明细里有一行缺少物品，请重新选择。') from None
        if item_id in seen:
            raise ValueError(f'物品 #{item_id} 在这张盘点单里出现了两次，请合并成一行。')
        seen.add(item_id)

        actual = _dec(raw.get('actual_quantity'))
        if actual is None:
            raise ValueError(f'物品 #{item_id} 的实盘数量没填或不是数字。')
        if actual < 0:
            raise ValueError(f'物品 #{item_id} 的实盘数量不能为负数。')

        note = (raw.get('note') or '').strip()
        out.append({'item_id': item_id, 'actual_quantity': actual, 'note': note[:200]})
    return out


@transaction.atomic
def create_stocktake(
    stocktake_date: date | None = None,
    note: str = '',
    lines=None,
    source: str = 'manual',
) -> dict:
    """提交一次实盘盘点：记下账面与实际，并把库存校准为实盘数

    整体放进一个事务：头建好了但明细没建、或者库存只改了一半，
    都会留下「盘点记录说改了、实际没改」的分叉 —— 而两边看起来都对。
    """
    normalized = _normalize_lines(lines)
    today = stocktake_date or timezone.localdate()
    if source not in SOURCE_LABELS:
        raise ValueError(f'未知的盘点来源：{source}')

    ids = [row['item_id'] for row in normalized]
    # select_for_update：从「读账面」到「写库存」这一段不能被并发请求插进来，
    # 否则两个同时提交的盘点会各自读到同一个旧账面，写出两条互相打架的记录。
    locked = (
        SurvivalItem.objects
        .select_for_update()
        .filter(user_id=1, id__in=ids)
        .select_related('category', 'unit')
    )
    items = {item.id: item for item in locked}

    missing = [i for i in ids if i not in items]
    if missing:
        raise ValueError(
            f'有 {len(missing)} 件物品不存在（可能是刚在别的页面删掉了）：'
            f'{"、".join(str(i) for i in missing[:5])}。请刷新后重试。',
        )

    head = SurvivalStocktake.objects.create(
        user_id=1,
        stocktake_date=today,
        source=source,
        note=(note or '').strip()[:200],
    )

    for row in normalized:
        item = items[row['item_id']]
        # 🔴 账面在**这里**读 —— 不取前端传来的值（铁律一）
        book = item.quantity
        SurvivalStocktakeLine.objects.create(
            stocktake=head,
            item=item,
            # 名字冗余留存：物品改名/删除都不该改写这条历史（同快照明细判据）
            item_name=item.name,
            category_name=item.category.name,
            unit_name=item.unit.name if item.unit else '',
            book_quantity=book,
            actual_quantity=row['actual_quantity'],
            note=row['note'],
        )
        # 盘点即校准（铁律二）+ 系统代记流水（v3.60.18）：改动经**唯一写口**，
        # 顺手留下一条 channel='stocktake' 的流水。
        # ⚠️ 差额为 0 的**不记**：「数了数、跟账上一样」本身不是一次库存变化，
        #    记下来只是噪音（record_flow 也会拒绝 0），所以在这里先判掉。
        delta = row['actual_quantity'] - book
        if delta != 0:
            record_flow(
                item.id, delta, channel='stocktake', reason='correct',
                note=f'实盘 {row["actual_quantity"]}，账面 {book}', user_id=1,
            )

    return get_stocktake(head.id)


# ══════════════════════════════════════════════════════════════
# 读：历史
# ══════════════════════════════════════════════════════════════

def list_stocktakes(limit=None) -> list[dict]:
    """盘点历史（**降序**：最近一次在最上面 —— 复盘总是从最近那次看起）

    ⚠️ 顺序与「趋势」类读函数相反是常态（表格要最近的在上、折线要左到右）。
       这里只有列表一个出口，所以只钉一个方向；将来若加趋势图，
       **不要**图省事把这条改成升序 —— 那会让表格反过来。新开一个升序函数。
    """
    size = _clamp_limit(limit)
    qs = (
        SurvivalStocktake.objects
        .filter(user_id=1)
        .prefetch_related('lines')
        .order_by('-stocktake_date', '-id')[:size]
    )
    return [_stocktake_row(head) for head in qs]


def get_stocktake(pk: int) -> dict:
    """单次盘点（含明细）"""
    head = (
        SurvivalStocktake.objects
        .filter(user_id=1, id=pk)
        .prefetch_related('lines')
        .first()
    )
    if head is None:
        raise ValueError('这次盘点记录不存在。')
    return _stocktake_row(head)


def delete_stocktake(pk: int) -> int:
    """删除一条盘点记录（**不回滚库存** —— 铁律三）

    明细随头一起删（`on_delete=CASCADE`）：脱离头的明细没有意义。
    但库存保持现状：它已经被核实过了，删掉凭据不该改变事实。
    """
    head = SurvivalStocktake.objects.filter(user_id=1, id=pk).first()
    if head is None:
        raise ValueError('这次盘点记录不存在。')
    head.delete()
    return pk
