"""生存资源 · 库存流水服务层（v3.60.18 · P0）

这一层存在的唯一理由：**库存的变化必须留痕，而且只有一个写口。**

🔴 铁律一 · **改库存只有一个写口 —— 本模块的 `record_flow()`。**
   任何绕过它的库存写入（ModelViewSet 直接 save、脚本、后台、以后新加的
   编辑入口）都会造出**无痕变化**：库存少了 2 件，流水里却没有这一笔 ——
   而界面看起来完全正常。所以 `survival_service.update_item()` 与
   `survival_stocktake.create_stocktake()` 都改成经由它写数量，
   而不是各自 `item.quantity = …; item.save()`。

🔴 铁律二 · **写流水与改库存同一事务。** 否则会出现「流水说有、账上没有」——
   两边看起来都对，谁也说不清哪个是真的。

🔴 铁律三 · **不做物理删除，只做「撤销」**（自动补一条反向流水）。
   用户想的是「我记错了」，不是「我要删数据」。撤销之后账正回来、历史全留。
   一条流水**最多被冲销一次**。

⚠️ 与另外两张生存资源历史表的分工（三张表各记一件事，**别合并**）：

    SurvivalSnapshot    系统算出来的**结论**（我以为能撑多久）—— 不用人动手
    SurvivalStocktake   人**核对过**（账面 vs 实盘）        —— 必须人动手
    SurvivalFlow(本表)  库存**怎么变的**（连续流水）        —— 人登记 / 系统代记

   合并的后果是「这 2 罐是被我吃了，还是被脚本改了」再也分不出来。

⚠️ 渠道与原因**正交**，别合并：渠道答「谁写的」，原因答「为什么」。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..constants import (
    SURVIVAL_FLOW_CHANNEL_LABELS,
    SURVIVAL_FLOW_CHANNELS,
    SURVIVAL_FLOW_DEFAULT_LIMIT,
    SURVIVAL_FLOW_DEFAULT_REASON,
    SURVIVAL_FLOW_MAX_BATCH,
    SURVIVAL_FLOW_MAX_LIMIT,
    SURVIVAL_FLOW_REASON_LABELS,
)
from ..models import SurvivalFlow, SurvivalItem

CHANNEL_KEYS = tuple(value for value, _ in SURVIVAL_FLOW_CHANNELS)
REASON_KEYS = tuple(SURVIVAL_FLOW_REASON_LABELS)

# 冲销流水用的原因 —— 常量里已有 `revert`，这里只是给它一个短名，
# 免得各处的字符串字面量各写一次（写错不报错，只会在筛选里查不出东西）。
REASON_REVERT = 'revert'


# ══════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════

def _f(value):
    """Decimal → float；`None` 原样返回（绝不兜底成 0）。"""
    if value is None:
        return None
    return float(value)


def _dec(value) -> Decimal | None:
    """宽容地把入参转成 Decimal；转不动返回 None（由调用方决定报什么错）。"""
    if value is None or value == '':
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _row(flow: SurvivalFlow, reverted_ids: set[int] | None = None) -> dict:
    return {
        'id': flow.id,
        'item_id': flow.item_id,
        'item_name': flow.item_name,
        'category_name': flow.category_name,
        'unit_name': flow.unit_name,
        'delta': _f(flow.delta),
        'channel': flow.channel,
        'channel_label': SURVIVAL_FLOW_CHANNEL_LABELS.get(flow.channel, flow.channel),
        'reason': flow.reason,
        'reason_label': SURVIVAL_FLOW_REASON_LABELS.get(flow.reason, flow.reason),
        'occurred_at': flow.occurred_at.isoformat() if flow.occurred_at else None,
        'reverses_id': flow.reverses_id,
        # 「这条已经撤销过了」由**服务端**一并下发 —— 前端拿不到这个事实就只能
        # 靠猜（或点一下看报不报错），而撤销按钮在已冲销的行上是不该显示可点的。
        'reverted': bool(reverted_ids and flow.id in reverted_ids),
        # 物品被删之后 item_id 为 null，但历史保留 ⇒ 界面要能标出「已删除」
        'item_missing': flow.item_id is None,
        'note': flow.note,
        'created_at': flow.created_at.isoformat() if flow.created_at else None,
    }


def _clean_reason(reason) -> str:
    value = (reason or '').strip()
    if not value:
        return ''
    if value not in REASON_KEYS:
        raise ValueError(f'未知的原因：{value}')
    return value


def _clean_channel(channel) -> str:
    value = (channel or '').strip()
    if value not in CHANNEL_KEYS:
        raise ValueError(f'未知的渠道：{value}')
    return value


def _default_reason(item: SurvivalItem, delta: Decimal) -> str:
    """原因留空时按类别的**消耗模式**自动预选。

    配餐供餐 → 吃掉，其余 → 用掉。判据对着 `consume_mode` 写、**不对着类别名写**
    （用户把「吃」改名成「口粮」不该改代码）。

    ⇒ 这样「原因」这一格在绝大多数情况下用户**一个字都不用填**，
      只有**异常**（坏了 / 过期 / 丢弃 / 送人）才需要动手 —— 这是本设计
      「避免重复填写」的第二条实现。

    ⚠️ 入库一侧（`delta > 0`）**不猜**：买进来的和人家送的都是正数，
       系统分不出来，猜错等于替用户写了个假的理由。留空就好。
    """
    if delta >= 0:
        return ''
    mode = item.category.consume_mode if item.category else ''
    return SURVIVAL_FLOW_DEFAULT_REASON.get(mode, '')


def _clean_moment(occurred_at):
    """发生时刻：默认现在；补记过去可以；**未来不行**。"""
    now = timezone.now()
    if occurred_at is None:
        return now
    if isinstance(occurred_at, date) and not hasattr(occurred_at, 'hour'):
        # 只给到日期时补到当天零点（用户补记「前天」）
        occurred_at = timezone.make_aware(
            datetime(occurred_at.year, occurred_at.month, occurred_at.day),
            timezone.get_current_timezone(),
        )
    if timezone.is_naive(occurred_at):
        occurred_at = timezone.make_aware(occurred_at, timezone.get_current_timezone())
    if occurred_at > now:
        raise ValueError('发生时刻不能是未来 —— 还没发生的事记不下来')
    return occurred_at


# ══════════════════════════════════════════════════════════════
# 写：唯一写口
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def record_flow(
    item_id: int,
    delta,
    channel: str = 'manual',
    reason: str = '',
    note: str = '',
    occurred_at=None,
    user_id: int = 1,
    reverses: SurvivalFlow | int | None = None,
) -> dict:
    """🔴 **库存的唯一写口**：改 `SurvivalItem.quantity` + 写一条流水，同一事务。

    参数
    ----
    delta      变化量，**正负皆可**：`-2` = 用掉 2、`+3` = 入库 3。
    channel    谁写进来的（常量 `SURVIVAL_FLOW_CHANNELS`）。
    reason     为什么变（常量 `SURVIVAL_FLOW_REASONS`），可空。
    reverses   冲销对象（只有「撤销」会传）。

    拒绝（抛 `ValueError`，视图层转 400）
    ----
    · `delta` 不是数字 / 为 0  —— 写一条 0 的流水只是噪音
    · 改完会 `< 0`           —— **不夹到 0**：静默夹 0 会把「记错了」变成「没货了」
    · `occurred_at` 在未来
    · 物品不存在
    """
    channel = _clean_channel(channel)

    delta_dec = _dec(delta)
    if delta_dec is None:
        raise ValueError('变化量必须是数字')
    if delta_dec == 0:
        raise ValueError('变化量为 0，没有可记的一笔')
    if not isinstance(item_id, int):
        raise ValueError('缺少物品')

    occurred = _clean_moment(occurred_at)

    # select_for_update：从「读数量」到「写数量」这一段不能被并发插进来，
    # 否则两个同时提交的消耗会各自读到同一个旧数量，后写的覆盖先写的 ——
    # 库存只少了一件，流水却记了两笔。同盘点服务的做法。
    item = (
        SurvivalItem.objects
        .select_for_update()
        .select_related('category', 'unit')
        .filter(id=item_id, user_id=user_id)
        .first()
    )
    if item is None:
        raise ValueError('物品不存在（可能刚在别的页面删掉了），请刷新后重试')

    # 原因留空 ⇒ 按类别的消耗模式自动预选（见 `_default_reason`）。
    # 放在取到 item **之后**，因为预选要读它的类别；用户填了就用用户填的。
    reason = _clean_reason(reason) if reason else _default_reason(item, delta_dec)

    after = item.quantity + delta_dec
    if after < 0:
        unit = item.unit.name if item.unit else ''
        raise ValueError(
            f'「{item.name}」现在只有 {item.quantity}{unit}，'
            f'这一笔要减 {abs(delta_dec)}{unit}，会变成负数 —— 请先核对库存数量。',
        )

    # 只动数量一个字段：顺手把别的字段写回去等于给并发编辑制造覆盖窗口
    item.quantity = after
    item.save(update_fields=['quantity', 'updated_at'])

    reverses_id = None
    if reverses is not None:
        reverses_id = reverses.id if isinstance(reverses, SurvivalFlow) else int(reverses)

    flow = SurvivalFlow.objects.create(
        user_id=user_id,
        item=item,
        # 三列冗余快照：物品改名 / 删类别 / 删单位都不该回改历史
        # （同快照明细与盘点明细的既有判据）
        item_name=item.name,
        category_name=item.category.name if item.category else '',
        unit_name=item.unit.name if item.unit else '',
        delta=delta_dec,
        channel=channel,
        reason=reason,
        occurred_at=occurred,
        reverses_id=reverses_id,
        note=(note or '').strip()[:200],
    )
    return _row(flow)


@transaction.atomic
def reverse_flow(flow_id: int, user_id: int = 1) -> dict:
    """撤销一条流水 = **补一条反向流水**（不做物理删除）。

    三条拒绝：
    · 这条本身就是冲销记录 —— 撤销它只会让账再变一次，且链会越来越长
    · 这条**已经被冲销过**     —— 否则点两次撤销就多扣一次
    · 物品已被删除             —— 没有可以改回来的库存（历史流水保留）
    """
    flow = SurvivalFlow.objects.filter(id=flow_id, user_id=user_id).first()
    if flow is None:
        raise ValueError('流水不存在')

    if flow.reverses_id is not None:
        raise ValueError('这是一条冲销记录，不能再被撤销；若要恢复，请手工登记一笔')
    if SurvivalFlow.objects.filter(reverses_id=flow.id).exists():
        raise ValueError('这条流水已经撤销过了')
    if flow.item_id is None:
        raise ValueError('物品已删除，没有可以改回来的库存；历史流水保留')

    return record_flow(
        item_id=flow.item_id,
        delta=-flow.delta,
        channel='manual',
        reason=REASON_REVERT,
        note=f'撤销 #{flow.id} {flow.item_name}',
        user_id=user_id,
        reverses=flow,
    )


def record_batch(rows, user_id: int = 1) -> list[dict]:
    """一次记多笔（批量入库 / 批量消耗）。

    ⚠️ 整批在**一个事务**里：中途有一笔会变负数，不能出现「前 3 笔写进去了、
       第 4 笔报错」—— 那样用户看到的是「保存失败」，但库存已经被改了一半。
       （`record_flow` 自带 atomic，这里再包一层让它成为同一个事务。）
    """
    if not isinstance(rows, list) or not rows:
        raise ValueError('没有要记的内容')
    if len(rows) > SURVIVAL_FLOW_MAX_BATCH:
        raise ValueError(f'一次最多记 {SURVIVAL_FLOW_MAX_BATCH} 笔，当前 {len(rows)} 笔')

    out = []
    with transaction.atomic():
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('每一笔都要是一个对象')
            out.append(record_flow(
                item_id=row.get('item_id'),
                delta=row.get('delta'),
                channel=row.get('channel') or 'manual',
                reason=row.get('reason') or '',
                note=row.get('note') or '',
                occurred_at=row.get('occurred_at'),
                user_id=user_id,
            ))
    return out


# ══════════════════════════════════════════════════════════════
# 读：流水列表
# ══════════════════════════════════════════════════════════════

def list_flows(
    item_id: int | None = None,
    category_name: str | None = None,
    channel: str | None = None,
    reason: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    keyword: str | None = None,
    limit: int | None = None,
    user_id: int = 1,
) -> list[dict]:
    """流水列表（**降序**：最近发生的在最上面）

    ⚠️ 端点**返回裸数组**，不走 DRF 全局分页；「最近 N 条」由这里的 `limit` 控制
       （默认 30、上限 500）—— 绕回分页会把数组包成 `{count, results}`，
       前端按数组消费就是「假 0」。
    """
    qs = SurvivalFlow.objects.filter(user_id=user_id)
    if item_id:
        qs = qs.filter(item_id=item_id)
    if category_name:
        qs = qs.filter(category_name=category_name)
    if channel:
        qs = qs.filter(channel=_clean_channel(channel))
    if reason:
        qs = qs.filter(reason=_clean_reason(reason))
    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)
    if keyword:
        # 物品已删的流水只剩 `item_name`，所以搜索必须能搜到它 ——
        # 搜不到且不报错是这类「冗余快照列」的经典漏法（补列要同步补 search_fields）
        qs = qs.filter(Q(item_name__icontains=keyword) | Q(note__icontains=keyword))

    limit = SURVIVAL_FLOW_DEFAULT_LIMIT if limit is None else limit
    limit = max(1, min(int(limit), SURVIVAL_FLOW_MAX_LIMIT))

    flows = list(qs.order_by('-occurred_at', '-id')[:limit])
    if not flows:
        return []

    # 「这条撤销过了没有」一次查清，避免逐行 exists() 打出 N+1
    reverted = set(
        SurvivalFlow.objects
        .filter(reverses_id__in=[f.id for f in flows])
        .values_list('reverses_id', flat=True),
    )
    return [_row(f, reverted) for f in flows]


# ══════════════════════════════════════════════════════════════
# 读：按月汇总
# ══════════════════════════════════════════════════════════════

def _month_range(month: str | None) -> tuple[datetime, datetime]:
    """`YYYY-MM` → 半开区间 `[月初 00:00, 下月初 00:00)`，返回**带时区的 datetime**

    🔴 **返回的必须是 aware datetime，不能是 `date`。**
       拿 `date` 去过滤 `occurred_at`（datetime 字段）时，Django 会把它摊成
       当天午夜的 **naive** datetime，再按当前时区猜一次 —— `USE_TZ=True` 下
       既报 RuntimeWarning，边界那几笔还会**静默漂移**（月初 00:00 的那笔
       可能被算进上个月）。项目在 `wealth_bill_list.date` 上已经踩实过这一类。

    🔴 **区间必须半开**，不要写 `occurred_at__month=…`：时区一漂就漏行。
    """
    if month:
        parts = str(month).split('-')
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise ValueError('月份格式应为 YYYY-MM')
        year, mon = int(parts[0]), int(parts[1])
        if not 1 <= mon <= 12:
            raise ValueError('月份格式应为 YYYY-MM')
        start = date(year, mon, 1)
    else:
        start = timezone.localdate().replace(day=1)

    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)

    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime(start.year, start.month, start.day), tz),
        timezone.make_aware(datetime(end.year, end.month, end.day), tz),
    )


def summarize_flows(month: str | None = None, user_id: int = 1) -> dict:
    """按月的「变少了多少 / 变多了多少」——回答「这个月吃掉了几罐」

    🔴 **跨单位不相加。** 「用掉 3 斤米 + 2 罐罐头 + 5 包纸」加起来没有意义
       （粮食与罐头不可通约）。所以所有分组都按 `unit_name` 分列，
       **桶内同单位才求和**，绝不给出一个「总消耗 10 件」的合计数 ——
       那个数看起来最像答案，其实是最没有意义的数。

    ⚠️ 冲销流水**照常计入**：原 `+3` 与撤销 `-3` 天然相抵，净效果正确。
       把冲销单排除掉反而会让「我这个月到底吃掉几罐」算错。
    """
    start, end = _month_range(month)

    rows = list(
        SurvivalFlow.objects
        .filter(user_id=user_id, occurred_at__gte=start, occurred_at__lt=end),
    )

    by_unit: dict[str, dict] = {}
    by_cat: dict[tuple[str, str], dict] = {}
    by_item: dict[tuple[str, str], dict] = {}

    def _bump(bucket: dict, key, unit_name: str, delta: float) -> None:
        cur = bucket.get(key)
        if cur is None:
            cur = {
                'unit_name': unit_name, 'consumed': 0.0, 'gained': 0.0,
                'net': 0.0, 'count': 0,
            }
            bucket[key] = cur
        if delta < 0:
            cur['consumed'] += -delta
        else:
            cur['gained'] += delta
        cur['net'] += delta
        cur['count'] += 1

    consumed_count = 0
    gained_count = 0
    for row in rows:
        d = float(row.delta)
        if d < 0:
            consumed_count += 1
        else:
            gained_count += 1
        unit = row.unit_name or ''
        _bump(by_unit, unit, unit, d)
        _bump(by_cat, (row.category_name or '', unit), unit, d)
        _bump(by_item, (row.item_name, unit), unit, d)

    def _round(rows_):
        for r in rows_:
            r['consumed'] = round(r['consumed'], 2)
            r['gained'] = round(r['gained'], 2)
            r['net'] = round(r['net'], 2)
        return rows_

    unit_rows = _round([
        {'unit_name': k, **v} for k, v in by_unit.items()
    ])
    cat_rows = []
    for (cat, unit), v in by_cat.items():
        cat_rows.append({'category_name': cat, 'unit_name': unit, **v})
    item_rows = []
    for (name, unit), v in by_item.items():
        item_rows.append({'item_name': name, 'unit_name': unit, **v})

    # 排序：消耗多的在前 —— 「这个月吃掉多少」的主问题就是消耗
    unit_rows.sort(key=lambda r: -r['consumed'])
    cat_rows = _round(sorted(cat_rows, key=lambda r: -r['consumed']))
    item_rows = _round(sorted(item_rows, key=lambda r: -r['consumed']))

    return {
        'month': f'{start.year:04d}-{start.month:02d}',
        # 区间内部是 aware datetime，**下发给界面的仍是「日期」**（人是按天看的）
        'date_from': str(start.date()),
        # 区间是半开的，下发给界面的「到」是**最后一天**（人才看得懂）
        'date_to': str((end - timedelta(days=1)).date()),
        'count': len(rows),
        'consumed_count': consumed_count,
        'gained_count': gained_count,
        'by_unit': unit_rows,
        'by_category': cat_rows,
        'by_item': item_rows,
    }
