"""资产科目 / 资产快照服务 — 科目可扩展的资产负债表快照（v3.58.21，P1-B）

与旧路径的关系
    旧：wealth_cash_flow 一行装 8 个账户列（managed=False，加科目等于改外部表）
    新：wealth_asset_account（科目主数据）+ WealthAssetSnapshot（头）+ Item（明细行）
    存量迁移已由用户手动执行完毕（management command
    `wealth_seed_asset_accounts --with-snapshots`）：旧表 18 期已按科目回填成
    新体系的快照。旧表**保留为历史存档**，不再被任何功能读取。
    v3.60.7 退役「双跑对账」—— 回填后两边同源，比对退化成恒等式，
    且它对旧表「同月两行」的期次会选到与回填不同的行，给出假差额。

汇总口径（即验收标准）
    参与汇总的科目 = include_in_balance_sheet = True 的科目；其余的只进明细，
       合计落在 excluded_total 里单独提示，不静默吞掉。
    liquid_total         = Σ 参与汇总且 is_liquid 的金额      —— 应急金分子
    category_totals      = 四个类别各自合计（恒 4 行，缺失补 0）
    financial_assets     = Σ 参与汇总且类别 ≠ 自用
    self_use_total       = 自用类合计
    total_assets         = financial_assets + self_use_total
    net_worth            = total_assets − borrow（快照头的负债）
    available_net_worth  = financial_assets − borrow  —— 「能变成钱的净值」，
                           剔除自用资产后的净资产，FIRE 类问题看的是这个

    ⚠️ 两条恒等式（测试锁住）：total_assets = financial_assets + self_use_total；
       net_worth = total_assets − borrow。

设计取舍（有意为之，不是遗漏）
    1. 快照头**不缓存**任何派生合计。缓存会制造第二个真源：改动科目主数据
       （如把某科目从「流动性」记为「投资性」）后，历史快照的缓存值会与明细
       对不上。对应口径：**金额是历史事实、不可变；分类是当前视角、随主数据联动**。
    2. 应收借出是一个**资产科目**（应收类），负债**不是**科目（以快照头
       borrow 参与减法）。旧表把二者并排放在一行纯属历史包袱。
    3. 科目被任何快照引用后**不可删除**（FK PROTECT），只能停用 ——
       否则删科目会把历史快照悄悄挖空，往期净资产凭空变化。
"""

from django.db import transaction
from django.db.models import Count

from apps.wealth.constants import ASSET_CATEGORIES, LEGACY_ASSET_ACCOUNTS
from apps.wealth.models import (
    WealthAssetAccount,
    WealthAssetSnapshot,
    WealthAssetSnapshotItem,
    WealthCashFlow,
)

SELF_USE_CATEGORY = '自用'
RECEIVABLE_CATEGORY = '应收'


def _round(value, digits: int = 2) -> float:
    return round(float(value or 0), digits)


# ══════════════════════════════════════════════════════════════
# 科目主数据
# ══════════════════════════════════════════════════════════════


def _account_row(obj: WealthAssetAccount, used_count: int = 0) -> dict:
    return {
        'id': obj.id,
        'code': obj.code,
        'name': obj.name,
        'category': obj.category,
        'account_kind': obj.account_kind,
        'institution': obj.institution or '',
        'is_liquid': bool(obj.is_liquid),
        'include_in_balance_sheet': bool(obj.include_in_balance_sheet),
        'sort': obj.sort,
        'is_active': bool(obj.is_active),
        'note': obj.note or '',
        'used_snapshot_count': used_count,
        'created_at': obj.created_at.isoformat() if obj.created_at else None,
        'updated_at': obj.updated_at.isoformat() if obj.updated_at else None,
    }


def get_account_list(user_id: int = 1, include_inactive: bool = False) -> list[dict]:
    """科目列表：按「类别顺序 → sort → id」稳定排序。

    类别顺序取 constants.ASSET_CATEGORIES 的下标，不依赖数据库排序 ——
    科目表刻意没有 Meta.ordering（外部表 ordering 会被注入 SELECT 而破坏聚合）。
    """
    qs = WealthAssetAccount.objects.filter(user_id=user_id)
    if not include_inactive:
        qs = qs.filter(is_active=True)
    accounts = list(qs)

    # 被引用次数一次聚合取回，避免逐科目 count（N+1）；
    # .order_by() 显式清序，防止未来给 Item 加 ordering 后聚合被静默影响。
    used = dict(
        WealthAssetSnapshotItem.objects
        .filter(snapshot__user_id=user_id)
        .order_by()
        .values_list('account_id')
        .annotate(n=Count('id'))
    )

    cat_index = {c: i for i, c in enumerate(ASSET_CATEGORIES)}
    accounts.sort(key=lambda a: (cat_index.get(a.category, 99), a.sort, a.id))
    return [_account_row(a, used.get(a.id, 0)) for a in accounts]


def get_account_summary(user_id: int = 1) -> dict:
    """科目结构汇总（主数据无金额，这里只谈结构与覆盖）"""
    accounts = get_account_list(user_id, include_inactive=True)
    active = [a for a in accounts if a['is_active']]

    by_category = []
    for cat in ASSET_CATEGORIES:
        rows = [a for a in active if a['category'] == cat]
        by_category.append({
            'category': cat,
            'count': len(rows),
            'counted': len([a for a in rows if a['include_in_balance_sheet']]),
            'liquid': len([a for a in rows if a['is_liquid']]),
        })

    return {
        'total': len(accounts),
        'active_count': len(active),
        'inactive_count': len(accounts) - len(active),
        'liquid_count': len([a for a in active if a['is_liquid']]),
        'counted_count': len([a for a in active if a['include_in_balance_sheet']]),
        'excluded_count': len([a for a in active if not a['include_in_balance_sheet']]),
        'used_count': len([a for a in active if a['used_snapshot_count'] > 0]),
        'by_category': by_category,
    }


def create_account(data: dict, user_id: int = 1) -> dict:
    """新增科目。code 留空合法（手工新增的科目无旧列可映射）。"""
    obj = WealthAssetAccount.objects.create(
        user_id=user_id,
        code=(data.get('code') or '').strip() or None,
        name=(data.get('name') or '').strip(),
        category=data.get('category') or '流动性',
        account_kind=data.get('account_kind') or '其他',
        institution=(data.get('institution') or '').strip() or None,
        is_liquid=bool(data.get('is_liquid', False)),
        include_in_balance_sheet=bool(data.get('include_in_balance_sheet', True)),
        sort=int(data.get('sort') or 0),
        is_active=bool(data.get('is_active', True)),
        note=(data.get('note') or '').strip() or None,
    )
    return _account_row(obj)


def update_account(account_id: int, data: dict, user_id: int = 1) -> dict:
    obj = WealthAssetAccount.objects.get(id=account_id, user_id=user_id)
    for field in (
        'name', 'category', 'account_kind', 'is_liquid',
        'include_in_balance_sheet', 'sort', 'is_active',
    ):
        if field in data:
            setattr(obj, field, data[field])
    if 'code' in data:
        obj.code = (data.get('code') or '').strip() or None
    if 'institution' in data:
        obj.institution = (data.get('institution') or '').strip() or None
    if 'note' in data:
        obj.note = (data.get('note') or '').strip() or None
    obj.save()
    return _account_row(obj)


def delete_account(account_id: int, user_id: int = 1) -> int:
    """删除科目。

    被快照引用时 Django 抛 ProtectedError（FK PROTECT）—— **由视图转成 400**，
    提示用户改为「停用」。这里不吞异常：删不掉就是删不掉，
    静默改停用会让用户以为删了。
    """
    obj = WealthAssetAccount.objects.get(id=account_id, user_id=user_id)
    obj.delete()
    return account_id


def seed_asset_accounts(user_id: int = 1, overwrite: bool = False) -> dict:
    """从旧表列定义生成种子科目（幂等）。

    overwrite=False（默认）：只补缺失的，**不动用户已改过的科目** ——
        否则日后调整种子定义会把用户在界面上改过的类别/流动性标记冲掉。
    overwrite=True：把种子值写回（用于「恢复默认」）。
    """
    created, kept, updated = 0, 0, 0
    for code, name, category, kind, institution, is_liquid, sort in LEGACY_ASSET_ACCOUNTS:
        defaults = {
            'name': name,
            'category': category,
            'account_kind': kind,
            'institution': institution or None,
            'is_liquid': is_liquid,
            'sort': sort,
        }
        if overwrite:
            _, was_created = WealthAssetAccount.objects.update_or_create(
                user_id=user_id, code=code, defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1
        else:
            _, was_created = WealthAssetAccount.objects.get_or_create(
                user_id=user_id, code=code, defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                kept += 1
    return {
        'created': created,
        'kept': kept,
        'updated': updated,
        'total': len(LEGACY_ASSET_ACCOUNTS),
        'overwrite': overwrite,
    }


# ══════════════════════════════════════════════════════════════
# 快照汇总（roll-up）
# ══════════════════════════════════════════════════════════════


def rollup_items(rows: list[tuple[float, WealthAssetAccount]], borrow: float = 0.0) -> dict:
    """明细行 → 汇总。

    rows: [(金额, 科目对象), ...]
    category_totals 恒返回 ASSET_CATEGORIES 全部键（缺失补 0）——
    前端按固定顺序渲染，不必自己补空行。
    """
    category_totals = {c: 0.0 for c in ASSET_CATEGORIES}
    liquid_total = 0.0
    excluded_total = 0.0
    counted = 0

    for amount, account in rows:
        amt = float(amount or 0)
        if not account.include_in_balance_sheet:
            # 不计表的科目（默认含自用资产）不进任何合计，但仍统计出来提示
            excluded_total += amt
            continue
        counted += 1
        category_totals[account.category] = category_totals.get(account.category, 0.0) + amt
        if account.is_liquid:
            liquid_total += amt

    financial_assets = sum(
        v for k, v in category_totals.items() if k != SELF_USE_CATEGORY
    )
    self_use_total = category_totals.get(SELF_USE_CATEGORY, 0.0)
    total_assets = financial_assets + self_use_total
    borrow = float(borrow or 0)

    return {
        'liquid_total': _round(liquid_total),
        'category_totals': {k: _round(v) for k, v in category_totals.items()},
        'financial_assets': _round(financial_assets),
        'self_use_total': _round(self_use_total),
        'total_assets': _round(total_assets),
        'borrow': _round(borrow),
        'net_worth': _round(total_assets - borrow),
        'available_net_worth': _round(financial_assets - borrow),
        'excluded_total': _round(excluded_total),
        'counted_count': counted,
        'item_count': len(rows),
    }


def _receivable_gap(total: dict, lend: float) -> float:
    """应收类科目合计 vs 快照头 lend 的差额（参考值，不参与合计）。

    与 P1-A 的 `lend_diff` 同性质：**只报差额、不改数据**。
    差额为 0 表示两边对得上；非 0 说明逐笔台账更新了但快照没跟上（或反之）。
    """
    return _round(total.get(RECEIVABLE_CATEGORY, 0.0) - float(lend or 0))


def _snapshot_row(snapshot: WealthAssetSnapshot, rows: list[tuple[float, WealthAssetAccount]],
                  with_items: bool = False) -> dict:
    total = rollup_items(rows, snapshot.borrow)
    data = {
        'id': snapshot.id,
        'yearmon': snapshot.yearmon,
        'snapshot_date': str(snapshot.snapshot_date) if snapshot.snapshot_date else None,
        'lend': _round(snapshot.lend),
        'remarks': snapshot.remarks or '',
        'receivable_gap': _receivable_gap(total['category_totals'], snapshot.lend),
        'created_at': snapshot.created_at.isoformat() if snapshot.created_at else None,
        'updated_at': snapshot.updated_at.isoformat() if snapshot.updated_at else None,
        **total,
    }
    if with_items:
        cat_index = {c: i for i, c in enumerate(ASSET_CATEGORIES)}
        items = [
            {
                'account_id': a.id,
                'code': a.code,
                'name': a.name,
                'category': a.category,
                'account_kind': a.account_kind,
                'is_liquid': bool(a.is_liquid),
                'include_in_balance_sheet': bool(a.include_in_balance_sheet),
                'amount': _round(amount),
            }
            for amount, a in rows
        ]
        items.sort(key=lambda i: (
            cat_index.get(i['category'], 99), 0 if i['include_in_balance_sheet'] else 1, i['account_id'],
        ))
        data['items'] = items
    return data


def _load_items(snapshot_ids: list[int]) -> dict[int, list[tuple[float, WealthAssetAccount]]]:
    """一次取回多期快照的明细行并按快照分组（避免逐期查询）"""
    grouped: dict[int, list[tuple[float, WealthAssetAccount]]] = {}
    if not snapshot_ids:
        return grouped
    qs = (
        WealthAssetSnapshotItem.objects
        .filter(snapshot_id__in=snapshot_ids)
        .select_related('account')
        .order_by('snapshot_id', 'account__sort', 'id')
    )
    for item in qs:
        grouped.setdefault(item.snapshot_id, []).append((item.amount, item.account))
    return grouped


def net_worth_by_yearmon(user_id: int = 1) -> dict[str, dict]:
    """{`YYYY-MM`: `{'net_worth', 'snapshot_date'}}` —— 全部期次**一次取回**。

    给**跨模块只读取用**（2026-10-03 起：月度复盘页的「存款余额」列，
    取代已退役的 `wealth_balance_list.total` 手填值）。

    🔴 单一真源：内部走 `rollup_items()` —— 与快照列表、比率体系同源。
       调用方**不许**自己拿明细行再算一遍，那会多出第二份口径，
       两边迟早算岔而界面上看不出来。
    🔴 返回的键**原样**取 `WealthAssetSnapshot.yearmon`（该表有
       `UNIQUE(user_id, yearmon)`，实测全表统一为 `YYYY-MM`）。
       消费端若要与别的来源对齐，请自行过一次 `norm_yearmon()` ——
       别在这里再写一份归一。
    """
    snapshots = list(
        WealthAssetSnapshot.objects.filter(user_id=user_id).order_by('yearmon')
    )
    items = _load_items([s.id for s in snapshots])
    index: dict[str, dict] = {}
    for snapshot in snapshots:
        total = rollup_items(items.get(snapshot.id, []), snapshot.borrow)
        index[snapshot.yearmon] = {
            'net_worth': total['net_worth'],
            'snapshot_date': str(snapshot.snapshot_date) if snapshot.snapshot_date else None,
        }
    return index


# ══════════════════════════════════════════════════════════════
# 快照读写
# ══════════════════════════════════════════════════════════════


def list_snapshots(user_id: int = 1, limit: int = 24, year: str | None = None) -> list[dict]:
    """快照列表，**裸数组**，按年月倒序。

    月度数据用 limit（最近 N 期）而非分页：一年 12 期，
    分页器在这种粒度上只是噪声。返回裸数组同样是刻意选择 ——
    被 DRF 全局分页包成 {count, results} 时前端按数组消费会静默显示为空。
    """
    qs = WealthAssetSnapshot.objects.filter(user_id=user_id)
    if year:
        qs = qs.filter(yearmon__startswith=f'{year}-')
    snapshots = list(qs.order_by('-yearmon')[:max(int(limit or 24), 1)])
    grouped = _load_items([s.id for s in snapshots])
    return [_snapshot_row(s, grouped.get(s.id, [])) for s in snapshots]


def get_snapshot_by_yearmon(yearmon: str, user_id: int = 1) -> dict | None:
    snapshot = WealthAssetSnapshot.objects.filter(user_id=user_id, yearmon=yearmon).first()
    if not snapshot:
        return None
    return _snapshot_row(snapshot, _load_items([snapshot.id]).get(snapshot.id, []), with_items=True)


def get_snapshot_detail(snapshot_id: int, user_id: int = 1) -> dict | None:
    snapshot = WealthAssetSnapshot.objects.filter(id=snapshot_id, user_id=user_id).first()
    if not snapshot:
        return None
    return _snapshot_row(snapshot, _load_items([snapshot.id]).get(snapshot.id, []), with_items=True)


@transaction.atomic
def save_snapshot(payload: dict, user_id: int = 1) -> dict:
    """新增或更新一期快照（按 yearmon 幂等）。

    明细行**全删重建**（与项目既有的 items 更新惯例一致）——
    逐行 diff 的收益在这里很小，而"漏删一行"的代价是钱被算两遍。

    校验一律抛 ValueError，由视图/序列化器转成 400：
      · 科目不存在 / 不属于本人
      · 科目已停用（停用即"不再记新账"，历史快照不受影响）
      · 同一科目重复出现（否则 roll-up 会把同一笔钱算两遍）
      · 金额为负（负数属于负债，应记入负债台账）
    """
    yearmon = (payload.get('yearmon') or '').strip()
    if not yearmon:
        raise ValueError('yearmon 不能为空')

    items = payload.get('items') or []
    account_ids = [int(i['account_id']) for i in items]
    if len(set(account_ids)) != len(account_ids):
        raise ValueError('同一科目在一期快照中只能出现一次')

    accounts = {
        a.id: a for a in WealthAssetAccount.objects.filter(user_id=user_id, id__in=account_ids)
    }
    missing = [aid for aid in account_ids if aid not in accounts]
    if missing:
        raise ValueError(f'科目不存在或不属于当前用户：{missing}')
    inactive = [aid for aid in account_ids if not accounts[aid].is_active]
    if inactive:
        raise ValueError(f'科目已停用，不能写入快照：{inactive}')
    negative = [int(i['account_id']) for i in items if float(i.get('amount') or 0) < 0]
    if negative:
        raise ValueError(f'资产余额不能为负（科目 {negative}）：负数请记入负债台账')

    snapshot, _ = WealthAssetSnapshot.objects.update_or_create(
        user_id=user_id,
        yearmon=yearmon,
        defaults={
            'snapshot_date': payload.get('snapshot_date') or None,
            'borrow': float(payload.get('borrow') or 0),
            'lend': float(payload.get('lend') or 0),
            'remarks': payload.get('remarks') or '',
        },
    )
    WealthAssetSnapshotItem.objects.filter(snapshot=snapshot).delete()
    WealthAssetSnapshotItem.objects.bulk_create([
        WealthAssetSnapshotItem(
            snapshot=snapshot,
            account=accounts[int(i['account_id'])],
            amount=float(i.get('amount') or 0),
        )
        for i in items
    ])
    return get_snapshot_detail(snapshot.id, user_id)


def delete_snapshot(snapshot_id: int, user_id: int = 1) -> int:
    snapshot = WealthAssetSnapshot.objects.get(id=snapshot_id, user_id=user_id)
    snapshot.delete()   # 明细行随 FK CASCADE 一并删除
    return snapshot_id


# ══════════════════════════════════════════════════════════════
# 旧表回填（存量迁移，已执行完毕 —— 命令保留以便重跑）
#
# v3.60.7 删掉了这里原有的两个对账函数。_legacy_asset_values 与
# LEGACY_ASSET_ACCOUNTS 仍被 seed_asset_accounts 与 backfill_from_legacy
# 使用，故保留。
# ══════════════════════════════════════════════════════════════


def _legacy_asset_values(legacy: WealthCashFlow) -> dict[str, float]:
    values = {}
    for code, *_ in LEGACY_ASSET_ACCOUNTS:
        values[code] = _round(getattr(legacy, code, None))
    return values


@transaction.atomic
def backfill_from_legacy(user_id: int = 1, yearmon: str | None = None) -> dict:
    """把旧表快照回填成新体系的科目快照明细（**由用户手动触发**）。

    前置：必须先 seed_asset_accounts 建出带 code 的科目。
    未建科目时不做任何写入，直接返回 `missing_accounts` —— 半途而废的回填
    比不回填更糟：缺科目的快照看起来"成功了"，总额却少一截。
    """
    required_codes = {code for code, *_ in LEGACY_ASSET_ACCOUNTS}
    existing = {
        a.code: a for a in WealthAssetAccount.objects.filter(
            user_id=user_id, code__in=required_codes,
        )
    }
    missing = sorted(required_codes - set(existing))
    if missing:
        return {
            'ok': False,
            'reason': 'missing_accounts',
            'missing_accounts': missing,
            'created': 0, 'updated': 0, 'scanned': 0,
        }

    # 🔴 走 get_snapshot_series() 的**同一套去重口径**，不要自己 order_by。
    # 旧表同月多行是常态，而「同月取哪一行」的唯一约定写在
    # cashflow_service.get_snapshot_series()（btime 最新、并列取 baid 最大）。
    # 这里若自己写 order_by('yearmon')，MySQL 对同月行的返回顺序**不保证** ——
    # 一旦它选中的行与趋势线选中的行不是同一行，回填出来的期次就会和顶部
    # 趋势对不上，而且两边都「看着正常」（2026-09-29 修正）。
    from .cashflow_service import get_snapshot_series, norm_yearmon
    target = norm_yearmon(yearmon) if yearmon else None
    legacy_rows = [
        cf for cf in get_snapshot_series()
        if target is None or norm_yearmon(cf.yearmon) == target
    ]

    created, updated = 0, 0
    for legacy in legacy_rows:
        values = _legacy_asset_values(legacy)
        items = [
            {'account_id': existing[code].id, 'amount': amount}
            for code, amount in values.items()
            if code in existing
        ]
        existed = WealthAssetSnapshot.objects.filter(
            user_id=user_id, yearmon=legacy.yearmon,
        ).exists()
        save_snapshot({
            'yearmon': legacy.yearmon,
            'snapshot_date': legacy.btime,
            'borrow': legacy.borrow or 0,
            'lend': legacy.lend or 0,
            'remarks': legacy.remarks or '',
            'items': items,
        }, user_id=user_id)
        if existed:
            updated += 1
        else:
            created += 1

    return {
        'ok': True,
        'scanned': len(legacy_rows),
        'created': created,
        'updated': updated,
        'missing_accounts': [],
    }
