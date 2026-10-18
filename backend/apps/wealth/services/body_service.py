"""身上之物 · 服务层（取数与组装）

只做三件事：取数、组装、CRUD 编排。
**一个判断都不在这里做** —— `satisfaction_blank_reason` 与四个计数全部来自
`body_calc`（唯一真源），视图层只做协议转换，前端只把数摆出来。

⚠️ 本模块**不复制**物件资产 / 物品清单的任何字段（价格、净值、天数一律不搬），
   只存**关系**：一行里出现的 `linked_kind` + `linked_name` 是给界面看的名字，
   真正的口径（那件东西值多少钱、还剩多少天）永远只在它自己的页面上。

⚠️ `services/__init__` 是一个**扁平命名空间**（`get_part_list` / `create_part`
   这类词早晚会撞），所以视图层按**模块**引用（`from ..services import body_service as svc`），
   不走包级符号 —— 物件资产那边也是这么处理的。
"""

from __future__ import annotations

from ..constants import (
    BODY_BLANK_REASONS,
    BODY_FIND_STATUS_CHOICES,
    BODY_FIND_STATUS_SETTLED,
    BODY_PART_SEEDS,
    BODY_SATISFACTION_CHOICES,
)
from ..models import SurvivalItem, WealthBodyNeed, WealthBodyPart, WealthProperty
from . import body_calc as calc

# 关联来源 → 给人看的一行字。放这里是为了界面只说一遍「物件资产 · 宝岛眼镜」，
# 而不是在模板里拼三种情况（那正是「前端判逻辑」的入口）。
LINKED_KIND_LABELS = {
    'property': '物件资产',
    'survival_item': '物品清单',
}


# ──────────────────────────────────────────────────────────────
# 部位（轻量主数据）
# ──────────────────────────────────────────────────────────────

def _part_row(part: WealthBodyPart) -> dict:
    return {
        'id': part.id,
        'name': part.name,
        'sort_order': part.sort_order,
        'note': part.note,
        # 让「部位维护」能一眼看出谁还在被用 —— 也解释了为什么它删不掉（有引用就是 400）
        'need_count': part.needs.count(),
    }


def get_part_list() -> list[dict]:
    qs = WealthBodyPart.objects.filter(user_id=1).order_by('sort_order', 'id')
    return [_part_row(p) for p in qs]


def _resolve_part(part_id) -> WealthBodyPart:
    """按 id 取部位；取不到直接抛 —— 让请求 400，而不是静默挂到一个错的部位上。"""
    if part_id is None:
        raise ValueError('必须指定部位')
    part = WealthBodyPart.objects.filter(id=part_id, user_id=1).first()
    if part is None:
        raise ValueError(f'部位 {part_id} 不存在')
    return part


def _assert_part_name_available(name: str, exclude_pk=None) -> str:
    name = (name or '').strip()
    if not name:
        raise ValueError('部位名称不能为空')
    qs = WealthBodyPart.objects.filter(user_id=1, name=name)
    if exclude_pk is not None:
        qs = qs.exclude(id=exclude_pk)
    if qs.exists():
        raise ValueError(f'已存在名为「{name}」的部位')
    return name


def create_part(payload: dict) -> dict:
    part = WealthBodyPart.objects.create(
        user_id=1,
        name=_assert_part_name_available(payload.get('name')),
        note=payload.get('note') or '',
        sort_order=payload.get('sort_order') or 0,
    )
    return _part_row(part)


def update_part(pk: int, payload: dict) -> dict:
    part = WealthBodyPart.objects.get(id=pk, user_id=1)
    if 'name' in payload:
        part.name = _assert_part_name_available(payload['name'], exclude_pk=pk)
    if 'note' in payload:
        part.note = payload['note'] or ''
    if 'sort_order' in payload and payload['sort_order'] is not None:
        part.sort_order = payload['sort_order']
    part.save()
    return _part_row(part)


def delete_part(pk: int) -> int:
    """删除部位 —— **先看里面还有没有位**，不级联

    级联删除会让「删掉一个建错的空部位」与「删掉整个部位下的所有位」走同一个按钮，
    代价完全不对称、且不可逆。这里宁可多一步，并把数量报出来让人能照做。
    """
    part = WealthBodyPart.objects.get(id=pk, user_id=1)
    count = part.needs.count()
    if count:
        raise ValueError(
            f'「{part.name}」下还有 {count} 条没搞定（或已搞定的）东西，不能直接删除；'
            f'请先把这些改到别的部位，或逐条删除。',
        )
    part.delete()
    return pk


def seed_parts(overwrite: bool = False) -> dict:
    """初始化默认部位（幂等）—— **只建部位，不预设任何「位」**

    只给这 11 个值的理由：它们是「身体有哪些部位」的常见刻度，
    让人从空下拉框开始建自己的一套太费事。位是你自己的数据，绝不代猜。

    幂等：同名部位已存在则跳过（`overwrite=True` 才覆盖说明与排序）。
    """
    created, updated, skipped = 0, 0, 0
    for index, seed in enumerate(BODY_PART_SEEDS):
        defaults = {'note': seed.get('note', ''), 'sort_order': index}
        part, is_new = WealthBodyPart.objects.get_or_create(
            user_id=1, name=seed['name'], defaults=defaults,
        )
        if is_new:
            created += 1
        elif overwrite:
            for key, value in defaults.items():
                setattr(part, key, value)
            part.save()
            updated += 1
        else:
            skipped += 1
    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'parts': get_part_list(),
    }


# ──────────────────────────────────────────────────────────────
# 位
# ──────────────────────────────────────────────────────────────

def _linked_kind(need: WealthBodyNeed) -> str | None:
    if need.property_id:
        return 'property'
    if need.survival_item_id:
        return 'survival_item'
    return None


def _linked_name(need: WealthBodyNeed) -> str:
    """关联的那件东西**叫什么**。

    ⚠️ 只取名字 —— 价格 / 净值 / 天数一律不搬过来（那是两份口径）。
       要看那些数，点名字跳过去看（`linked_kind` 告诉前端该跳哪一页）。
    """
    if need.property_id and need.property is not None:
        return need.property.name
    if need.survival_item_id and need.survival_item is not None:
        return need.survival_item.name
    return ''


def _need_row(need: WealthBodyNeed) -> dict:
    """一个位的完整行。

    🔴 `satisfaction_blank_reason` 由 `body_calc` 算 —— **前端不拿别的字段自己推**
       （推错了没人发现，且界面上看起来完全正常）。
    """
    kind = _linked_kind(need)
    return {
        'id': need.id,
        'part_id': need.part_id,
        'part_name': need.part.name if need.part is not None else '',
        'name': need.name,
        'find_status': need.find_status,
        'satisfaction': need.satisfaction,
        # 空值的**来由**；有值时是 None（那时不需要解释）
        'satisfaction_blank_reason': calc.resolve_blank_reason(need),
        'wish': need.wish,
        'note': need.note,
        'property_id': need.property_id,
        'survival_item_id': need.survival_item_id,
        # 关联来源与它叫什么 —— 由后端说清，前端不做三分支判断
        'linked_kind': kind,
        'linked_kind_label': LINKED_KIND_LABELS.get(kind, '') if kind else '',
        'linked_name': _linked_name(need),
        # 好恶物档案馆回流的评价徽标 —— 与物件资产页显示的是**同一条**档案。
        # ⚠️ 只读、不参与任何计算、也不与本模块的满意互相推导
        #    （一件东西可以「档案馆 👎 踩坑」而「这里 凑合」——一个问值不值，
        #     一个问这个位够不够用，结论相反是允许的）。
        'treasure_badge': None,
        'treasure_record_id': None,
        'created_at': need.created_at,
        'updated_at': need.updated_at,
    }


def _attach_badges(rows: list[dict]) -> list[dict]:
    """一次查完这一页的评价徽标（不是逐行查 —— 逐行查就是 N+1）。"""
    # 函数内 import：避免 app registry 未就绪时被模块级 import 拖住（同 badges.py 的做法）
    from apps.treasure.badges import badge_map

    prop_map = badge_map(
        'property', [r['property_id'] for r in rows if r['property_id']],
    )
    item_map = badge_map(
        'survival_item', [r['survival_item_id'] for r in rows if r['survival_item_id']],
    )
    for row in rows:
        hit = prop_map.get(row['property_id']) or item_map.get(row['survival_item_id'])
        row['treasure_badge'] = hit[0] if hit else None
        row['treasure_record_id'] = hit[1] if hit else None
    return rows


def get_need_list(
    part_id=None,
    find_status=None,
    pending_only=False,
    search=None,
) -> list[dict]:
    """位列表 —— 支持按部位 / 进度 / 关键词筛选，或只取「还没搞定」的。

    ⚠️ 返回**裸数组**（视图层 `pagination_class = None`）：被 DRF 全局分页包成
       `{count, results}` 后，前端按数组消费会**静默显示为空**（项目硬坑③）。

    ⚠️ `pending_only` 的判据与 `body_calc.summarize` 的 `pending_count` 是**同一条**
       （`find_status != 'settled'`）—— 否则顶部念「还有 5 件没搞定」、
       点进去看到 3 行，两个数对不上还没人会去查。
       实现上直接复用 `body_calc` 里那个函数，不在这里重写一遍条件。

    ⚠️ 排序交给这里（模型刻意不设 `Meta.ordering`）：先按部位的自定义顺序，
       再按最近录入 —— 部位顺序是用户自己排的，比 id 有意义。
    """
    qs = (
        WealthBodyNeed.objects
        .select_related('part', 'property', 'survival_item')
        .filter(user_id=1)
    )
    if part_id:
        qs = qs.filter(part_id=part_id)
    if find_status:
        qs = qs.filter(find_status=find_status)
    if search:
        qs = qs.filter(name__icontains=search)
    qs = qs.order_by('part__sort_order', 'part_id', '-created_at', '-id')
    rows = [_need_row(n) for n in qs]
    if pending_only:
        rows = [r for r in rows if is_pending(r)]
    return _attach_badges(rows)


def is_pending(row: dict) -> bool:
    """「还没搞定」的**唯一判据** —— 顶部计数与列表筛选共用这一个。

    ⚠️ 刻意放在这里而不是各处写 `row['find_status'] != 'settled'`：
       两处写法一旦分叉（比如某处漏了大小写、某处多算一档），
       界面上会出现「念 5 件、点进去 3 行」—— 两个数都对不上，还没人会去查。
    """
    return row['find_status'] != BODY_FIND_STATUS_SETTLED


def get_need(pk: int) -> dict | None:
    need = (
        WealthBodyNeed.objects
        .select_related('part', 'property', 'survival_item')
        .filter(id=pk, user_id=1).first()
    )
    if need is None:
        return None
    return _attach_badges([_need_row(need)])[0]


def _resolve_link(payload: dict, current: dict | None = None) -> dict:
    """把两个关联字段归一成「最多挂一件」。

    🔴 互斥由**服务端**保证，不指望客户端只送一个 ——
       客户端送了两个也照收、服务端自己归一（同项目「置空类不变量写在服务端」）。
       ⚠️ 但**不静默挑一个**：两个都送上来时直接 400 说清楚，
          静默保留其中一个会让用户以为另一个也生效了。
    """
    merged = dict(current or {})
    merged.update(payload)
    prop_id = merged.get('property_id')
    item_id = merged.get('survival_item_id')
    if prop_id and item_id:
        raise ValueError(
            '一个位最多只能挂一件东西：物件资产与物品清单里选一个。'
            '若两件都在用，请把它拆成两个位。',
        )
    return {
        'property': _resolve_property(prop_id),
        'survival_item': _resolve_survival_item(item_id),
    }


def _resolve_property(prop_id):
    if not prop_id:
        return None
    prop = WealthProperty.objects.filter(id=prop_id, user_id=1).first()
    if prop is None:
        raise ValueError(f'物件资产 {prop_id} 不存在')
    return prop


def _resolve_survival_item(item_id):
    if not item_id:
        return None
    item = SurvivalItem.objects.filter(id=item_id, user_id=1).first()
    if item is None:
        raise ValueError(f'物品清单 {item_id} 不存在')
    return item


def create_need(payload: dict) -> dict:
    part = _resolve_part(payload.pop('part_id', None))
    links = _resolve_link(payload)
    need = WealthBodyNeed.objects.create(
        user_id=1, part=part,
        name=(payload.get('name') or '').strip(),
        find_status=payload.get('find_status') or 'todo',
        satisfaction=payload.get('satisfaction') or None,
        wish=payload.get('wish') or '',
        note=payload.get('note') or '',
        **links,
    )
    return _attach_badges([_need_row(need)])[0]


def update_need(pk: int, payload: dict) -> dict:
    need = WealthBodyNeed.objects.get(id=pk, user_id=1)
    if 'part_id' in payload:
        need.part = _resolve_part(payload.pop('part_id'))
    if 'property_id' in payload or 'survival_item_id' in payload:
        links = _resolve_link(payload, {
            'property_id': need.property_id,
            'survival_item_id': need.survival_item_id,
        })
        need.property = links['property']
        need.survival_item = links['survival_item']
    for key in ('name', 'find_status', 'wish', 'note'):
        if key in payload:
            need.__setattr__(key, payload[key])
    # 满意是**可清空的**（用户可以把评过的撤掉）—— 所以不能写 `if value is not None`。
    # ⚠️ 空串归一成 None：`''` 落在 `null=True` 的列上会让「空」多出第二种存法，
    #    而 `resolve_blank_reason` 判的是 falsy —— `''` 会被当成「没值」，
    #    于是库里两种空、界面上一样，将来对账时才发现。
    if 'satisfaction' in payload:
        need.satisfaction = payload['satisfaction'] or None
    need.save()
    return _attach_badges([_need_row(need)])[0]


def delete_need(pk: int) -> int:
    """删除一个位 —— **物理删除**（没有软删开关）。

    「不需要这一条了」的出口就是它。这也是刻意不给「不想找了」状态的原因：
    那个状态会同时装「真的不需要」与「暂时懒得找」两种相反的东西（兜底桶）。
    """
    need = WealthBodyNeed.objects.get(id=pk, user_id=1)
    need.delete()
    return pk


# ──────────────────────────────────────────────────────────────
# 汇总与元信息
# ──────────────────────────────────────────────────────────────

def get_summary() -> dict:
    """顶部计数 —— 全部 / 待寻 / 寻找中 / 已找到 + 「还没搞定」。

    计数口径全部来自 `body_calc.summarize`（唯一真源），
    这里的职责只是**把行喂进去**，不重算任何数。
    """
    rows = list(WealthBodyNeed.objects.filter(user_id=1).values('find_status'))
    return calc.summarize(rows)


def get_meta() -> dict:
    """口径与枚举的单一出口 —— 前端不硬编码任何文案或选项"""
    return {
        # 枚举一律随接口下发，前端零副本（标签一个字都不许在前端复写）
        'find_statuses': [{'value': v, 'label': l} for v, l in BODY_FIND_STATUS_CHOICES],
        'satisfactions': [{'value': v, 'label': l} for v, l in BODY_SATISFACTION_CHOICES],
        # 满意留空的两种来由：`short` 是格子里的字、`label` 是悬停的解释。
        # 两个都给，前端才不用自己把长句截成短句（那是第二份映射）。
        'blank_reasons': [dict(r) for r in BODY_BLANK_REASONS],
        'metric_meta': calc.build_metric_meta(),
        'part_seeds_available': True,
        # 页面里固定那几句说明 —— 放这里是为了它们只有一个来源
        'subtitle': '管的是「我该有什么、称不称心」，不是库存也不是价格',
        'satisfaction_note': (
            '留空不等于「凑合」—— 还没有东西在用、和有东西在用但没评过，是两件事'
        ),
    }
