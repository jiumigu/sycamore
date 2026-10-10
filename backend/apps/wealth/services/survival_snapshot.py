"""生存资源盘点 · 盘点快照（二期）

盘的是**时间序列**，不是某一刻的存量。一期回答「现在能撑多久」，
这里回答第二个问题：**比上次是变长了还是变短了** —— 没有这个方向，
「还能撑 240 天」这个数字每看一次都像第一次看。

三条刻意的取舍：

一、**存结论，不存明细**。快照落的是那一天算出来的天数 / 短板 / 瓶颈 / 覆盖率，
    不是那一天的库存列表。若只存明细、每次按今天的配置重算，
    历史曲线就会被**追溯性改写** —— 那不是历史，是一张会随时间变形的假图。
    （一期「派生值不落库」禁的是「缓存当前随时可重算的值」，与此不冲突：
      一期禁的是当下，这里要的是历史。）

二、**快照不可编辑，只能删掉重盘**。可编辑的历史等于伪造的历史：
    把上个月那个不好看的数改掉，曲线就永远只升不降了。

三、**两次之间可比与否必须说出来**。天数的涨跌可能来自消耗，
    也可能来自新录了一批库存、或者把某个类别从「按需」改成了「配餐」。
    后一种情况下直接相减是把「换算法」当成「物资变化」，
    所以这里对比两个点的**配置指纹**（类别集合 + 各自消耗模式），
    变过就标注不可比，而不是照常给一个差值。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.utils import timezone

from ..constants import (
    SURVIVAL_BOTTLENECK_LABELS,
    SURVIVAL_SNAPSHOT_DEFAULT_LIMIT,
    SURVIVAL_SNAPSHOT_DELTA_EPSILON,
    SURVIVAL_SNAPSHOT_MAX_LIMIT,
    SURVIVAL_SNAPSHOT_TREND_MIN_POINTS,
)
from ..models import SurvivalSnapshot, SurvivalSnapshotCategory
from . import survival_service as svc


# ──────────────────────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────────────────────

def _dec(value, digits: int = 2):
    """float → Decimal，先按字符串构造

    直接 `Decimal(3.1)` 会得到 3.100000000000000088817841970012523，
    落库时靠字段的 decimal_places 截回来 —— 能跑，但一旦有谁改了精度
    就会带出浮点尾巴。先 round 再走字符串，结果与打印出来的数一致。
    """
    if value is None:
        return None
    return Decimal(str(round(float(value), digits)))


def _f(value) -> float | None:
    return float(value) if value is not None else None


def _clamp_limit(limit, default: int = SURVIVAL_SNAPSHOT_DEFAULT_LIMIT) -> int:
    """趋势/列表的取数上限 —— 超界不报错，夹到边界

    limit 是个「看多少」的视角参数，为了它甩一个 400 只会打断使用。
    但上限必须存在：不设上限等于让一次请求把全部历史拉出来。
    """
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return default
    if value <= 0:
        return default
    return min(value, SURVIVAL_SNAPSHOT_MAX_LIMIT)


# ──────────────────────────────────────────────────────────────
# 落快照
# ──────────────────────────────────────────────────────────────

def take_snapshot(
    snapshot_date: date | None = None,
    note: str = '',
    overwrite: bool = False,
) -> dict:
    """把「此刻算出来的结论」落成一份快照

    ⚠️ 同一天重复盘点**默认拒绝**，不动存量数据。
       `overwrite=True` 是显式的「我知道，替换掉它」——
       静默 upsert 会让人以为点了两次只是刷了个新，实际那次旧结论已经没了。
    """
    today = snapshot_date or timezone.localdate()
    analysis = svc.get_analysis(today)

    if not analysis['available']:
        # 表没建 / 数据没就绪 —— 这是可预期的部署状态，不是可以落一份空快照的理由。
        # 落一份全是空值的快照比不落更糟：它会在曲线上留一个永远解释不清的点。
        raise ValueError(analysis['reason'] or '数据尚未就绪，无法盘点')

    existing = SurvivalSnapshot.objects.filter(
        user_id=1, snapshot_date=today,
    ).first()
    if existing and not overwrite:
        raise ValueError(
            f'{today} 已经盘点过一次了。同一天的两个点会让曲线出现竖直段，'
            f'也无法回答「哪一份才是真的」；如需重盘，请先删掉那一天，'
            f'或勾选覆盖。',
        )
    if existing:
        existing.delete()

    categories = analysis['categories'] or []
    overall_days = analysis['overall'].get('days', {}) or {}

    snapshot = SurvivalSnapshot.objects.create(
        user_id=1,
        snapshot_date=today,
        source='manual',
        note=(note or '')[:200],
        days_optimistic=_dec(overall_days.get('optimistic')),
        days_likely=_dec(overall_days.get('likely')),
        days_pessimistic=_dec(overall_days.get('pessimistic')),
        days_expected=_dec(analysis['overall'].get('expected')),
        spread=_dec(analysis['overall'].get('spread')),
        # 存当时的名字：类别以后改名，这个历史点不该跟着改
        shortest_category=(analysis.get('shortest_category') or '')[:50],
        bottleneck=analysis.get('bottleneck') or '',
        cash_months=_dec(analysis['cash'].get('months')),
        cash_days=_dec(analysis['cash'].get('days')),
        coverage_pct=_dec(analysis['coverage'].get('pct')),
        coverage_remaining_days=analysis['coverage'].get('remaining_days'),
        category_count=len(categories),
        item_count=sum(int(row.get('usable_item_count') or 0) for row in categories),
        snack_days=_dec(analysis.get('snack_days')),
        issue_count=len(analysis.get('issues') or []),
        trustworthy=not (analysis.get('issues') or []),
    )

    for row in categories:
        days = row.get('days') or {}
        # 配方级问题刻意不下沉到类别层（避免汇总时重复计一遍），
        # 所以这里的条数要把两层一起数 —— 否则「这个类别有几个毛病」会少报。
        recipe_issue_count = sum(
            len(recipe.get('issues') or []) for recipe in (row.get('recipes') or [])
        )
        SurvivalSnapshotCategory.objects.create(
            snapshot=snapshot,
            category_id=row.get('category_id'),
            category_name=(row.get('name') or '')[:50],
            consume_mode=row.get('consume_mode') or '',
            aggregate_mode_effective=row.get('aggregate_mode_effective') or '',
            days_optimistic=_dec(days.get('optimistic')),
            days_likely=_dec(days.get('likely')),
            days_pessimistic=_dec(days.get('pessimistic')),
            days_expected=_dec(row.get('expected')),
            usable_item_count=int(row.get('usable_item_count') or 0),
            item_count=int(row.get('item_count') or 0),
            snack_days=_dec(row.get('snack_days')),
            hours_total=_dec(row.get('hours_total'), digits=1),
            issue_count=len(row.get('issues') or []) + recipe_issue_count,
            trustworthy=bool(row.get('trustworthy', True)),
        )

    return _snapshot_row(snapshot, with_categories=True)


# ──────────────────────────────────────────────────────────────
# 读
# ──────────────────────────────────────────────────────────────

def _snapshot_row(snapshot: SurvivalSnapshot, with_categories: bool = False) -> dict:
    row = {
        'id': snapshot.id,
        'date': str(snapshot.snapshot_date),
        'source': snapshot.source,
        'source_label': snapshot.get_source_display(),
        'note': snapshot.note,
        # 与类别结果同形：三档装在 days 里，前端可复用同一套格式化
        'days': {
            'optimistic': _f(snapshot.days_optimistic),
            'likely': _f(snapshot.days_likely),
            'pessimistic': _f(snapshot.days_pessimistic),
        },
        'expected': _f(snapshot.days_expected),
        'spread': _f(snapshot.spread),
        'shortest_category': snapshot.shortest_category or None,
        'bottleneck': snapshot.bottleneck or 'balanced',
        'bottleneck_label': SURVIVAL_BOTTLENECK_LABELS.get(snapshot.bottleneck, ''),
        'cash_months': _f(snapshot.cash_months),
        'cash_days': _f(snapshot.cash_days),
        'coverage_pct': _f(snapshot.coverage_pct),
        'coverage_remaining_days': snapshot.coverage_remaining_days,
        'category_count': snapshot.category_count,
        'item_count': snapshot.item_count,
        'snack_days': _f(snapshot.snack_days),
        'issue_count': snapshot.issue_count,
        'trustworthy': snapshot.trustworthy,
        'created_at': snapshot.created_at.isoformat() if snapshot.created_at else None,
    }
    if with_categories:
        row['categories'] = [
            {
                'category_id': c.category_id,
                'category_name': c.category_name,
                'consume_mode': c.consume_mode,
                'aggregate_mode_effective': c.aggregate_mode_effective,
                'days': {
                    'optimistic': _f(c.days_optimistic),
                    'likely': _f(c.days_likely),
                    'pessimistic': _f(c.days_pessimistic),
                },
                'expected': _f(c.days_expected),
                'usable_item_count': c.usable_item_count,
                'item_count': c.item_count,
                'snack_days': _f(c.snack_days),
                'hours_total': _f(c.hours_total),
                'issue_count': c.issue_count,
                'trustworthy': c.trustworthy,
            }
            for c in snapshot.categories.all().order_by('id')
        ]
    return row


def list_snapshots(limit=None) -> list[dict]:
    """历史列表 —— **最近的在前**（给表格用）

    ⚠️ 与 `get_trend` 的顺序**刻意相反**：表格要「最近的在上」，
       折线要「从左到右按时间」。同一个数组在两处用不同顺序会被后来者
       「顺手统一」成一个，然后必然有一处显示反。命名与文档里都写明。
    """
    size = _clamp_limit(limit)
    rows = SurvivalSnapshot.objects.filter(user_id=1).order_by('-snapshot_date')[:size]
    return [_snapshot_row(r) for r in rows]


def delete_snapshot(pk: int) -> int:
    """删掉一期盘点。级联会带走它的类别明细（明细脱离头没有意义）。"""
    snapshot = SurvivalSnapshot.objects.get(id=pk, user_id=1)
    snapshot.delete()
    return pk


def get_trend(limit=None) -> dict:
    """趋势序列 —— **按日期升序**（给折线用）+ 与上一期的对比

    ⚠️ 反了就是画反的线：这里必须升序（见 `list_snapshots` 的说明）。
    """
    size = _clamp_limit(limit)
    rows = list(
        SurvivalSnapshot.objects.filter(user_id=1)
        .order_by('-snapshot_date')[:size]
    )
    rows.reverse()  # 升序

    points = [_snapshot_row(r) for r in rows]

    # 逐点附上「与上一个点相比」——放在这里算，前端不做减法。
    # 缺值的情况**不填 0**：一个点算不出来时差值是「不知道」不是「没变化」。
    for index, point in enumerate(points):
        point['delta_expected'] = None
        point['delta_kind'] = None
        point['days_since_previous'] = None
        if index == 0:
            continue
        previous = points[index - 1]
        point['delta_expected'] = _delta(previous['expected'], point['expected'])
        point['delta_kind'] = _delta_kind(point['delta_expected'])
        point['days_since_previous'] = _days_between(previous['date'], point['date'])

    return {
        'available': True,
        'count': len(points),
        'min_points': SURVIVAL_SNAPSHOT_TREND_MIN_POINTS,
        'has_enough_points': len(points) >= SURVIVAL_SNAPSHOT_TREND_MIN_POINTS,
        'points': points,
        'comparison': _comparison(points),
        'series': _series(points),
    }


def _series(points: list[dict]) -> dict:
    """给折线用的扁平数组

    ⚠️ 空值**保持 None**，不要补 0 也不要跳过 —— 前端据此画断点。
       补 0 会画出一条「那天物资归零」的假线。
    """
    return {
        'dates': [p['date'] for p in points],
        'expected': [p['expected'] for p in points],
        'optimistic': [p['days']['optimistic'] for p in points],
        'pessimistic': [p['days']['pessimistic'] for p in points],
        'cash_days': [p['cash_days'] for p in points],
        'item_count': [p['item_count'] for p in points],
    }


def _delta(previous, current):
    if previous is None or current is None:
        return None
    return round(float(current) - float(previous), 2)


def _delta_kind(delta) -> str | None:
    """变化方向 —— 阈值内算「持平」

    「+0.0 天」这类噪声会被读成「有变化只是没显示出来」，
    所以先夹一道 epsilon，再判方向。
    """
    if delta is None:
        return None
    if abs(delta) < SURVIVAL_SNAPSHOT_DELTA_EPSILON:
        return 'flat'
    return 'up' if delta > 0 else 'down'


def _days_between(start: str, end: str) -> int | None:
    try:
        a = date.fromisoformat(start)
        b = date.fromisoformat(end)
    except (TypeError, ValueError):
        return None
    return (b - a).days


def _comparison(points: list[dict]) -> dict:
    """最近两点之间的对比 —— 含「这次能不能直接比」的判断

    判据不是「有没有两个点」，而是**两个点的配置指纹是否一致**：
    类别集合、各自的消耗模式、生效的聚合口径。
    任一项变过，天数的差就混进了「换了算法」这一项，必须标出来。
    """
    if len(points) < SURVIVAL_SNAPSHOT_TREND_MIN_POINTS:
        return {
            'comparable': False,
            'config_changed': False,
            'changed_categories': [],
            'reason': (
                '只有一次盘点，还没有可对比的上一期'
                if points else '还没有任何盘点记录'
            ),
            'delta_expected': None,
            'delta_item_count': None,
            'days_since_previous': None,
        }

    latest, previous = points[-1], points[-2]
    changed = _config_diff(previous['id'], latest['id'])
    comparable = not changed

    return {
        'comparable': comparable,
        'config_changed': bool(changed),
        'changed_categories': changed,
        'reason': (
            f'期间有 {len(changed)} 个类别的构成或消耗方式变过（'
            + '、'.join(changed[:5])
            + '），天数涨跌里混着「换了算法」这一项，不能只当成物资变化'
        ) if changed else '',
        'delta_expected': latest['delta_expected'],
        'delta_item_count': latest['item_count'] - previous['item_count'],
        'days_since_previous': latest['days_since_previous'],
        'latest_date': latest['date'],
        'previous_date': previous['date'],
        'latest_expected': latest['expected'],
        'previous_expected': previous['expected'],
    }


def _config_diff(previous_id: int, latest_id: int) -> list[str]:
    """两个快照之间，哪些类别的「算法配置」变了

    返回类别名列表（按名字排序，便于用例断言与界面稳定展示）。
    判据是三项：类别是否还在、消耗模式、生效的聚合口径。
    """
    rows = SurvivalSnapshotCategory.objects.filter(
        snapshot_id__in=[previous_id, latest_id],
    ).values('snapshot_id', 'category_name', 'consume_mode', 'aggregate_mode_effective')

    def fingerprint(snapshot_id: int) -> dict[str, tuple[str, str]]:
        return {
            r['category_name']: (r['consume_mode'], r['aggregate_mode_effective'])
            for r in rows
            if r['snapshot_id'] == snapshot_id
        }

    before, after = fingerprint(previous_id), fingerprint(latest_id)
    changed = [
        name for name in set(before) | set(after)
        if before.get(name) != after.get(name)
    ]
    return sorted(changed)


def get_snapshot(pk: int) -> dict:
    """单份快照（含类别明细）"""
    snapshot = SurvivalSnapshot.objects.get(id=pk, user_id=1)
    return _snapshot_row(snapshot, with_categories=True)


__all__ = [
    'take_snapshot',
    'list_snapshots',
    'delete_snapshot',
    'get_trend',
    'get_snapshot',
]
