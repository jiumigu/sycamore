"""自我运转 · 服务层（**T1 制定 → T2 执行 → T3 复盘 → T4 回望**）

> 设计依据：`docs/自我运转-功能设计-v0.3-20261013.md` §3–§6。本文件是**全部业务口径**的落点。

🔴 五条贯穿性铁律：

1. **派生值不落库**；唯一例外是**快照**（`Period.readings` / `Stage.summary_snapshot`）。
   判据：「**以后重算得出同样结果吗？**」不能 ⇒ 才落。
2. **`GET` 一律不写库** —— 当前周期返回**虚拟对象**（`id=None`），首次写入才建行。
   （项目铁律：只读接口别 `get_or_create`。）
3. **撤销 ≠ 删除** —— 补一条负值流水，原记录保留（否则快照冻结后账实不符）。
4. **判定阈值只在 `constants.PERIOD_VERDICT_BANDS` 一份**，前端 0 个阈值数字。
5. **`None` ≠ `0`** —— 取不到返回 `None`（显示「—」+ 原因），真 0 返回 `0`（显示 `0h`）。
"""
import datetime as dt
import uuid

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .constants import (
    BACKFILL_WARN_DAYS,
    MODULE_VALUE_WHITELIST,
    MONTHLY_QUESTION_BANDS,
    OPEN_STAGE_STATUSES,
    PERIOD_VERDICT_BANDS,
    PLAN_SCOPE_CHOICES,
    READER_KEYS,
    STALE_RULES,
    TARGET_SOURCE_FROM,
    TARGET_SOURCE_LABELS,
    TARGET_SOURCE_METRIC,
    TARGET_SOURCE_SINGLE,
)
from .models import (
    SelfRunCheckin, SelfRunMetric, SelfRunMetricLog, SelfRunMetricPlan,
    SelfRunPeriod, SelfRunStage, SelfRunTemplate,
)
from .readers import config_fingerprint, period_range, run_reader
from .templates import TEMPLATE_COPY_FIELDS


# ══════════════════════════════════════════════════════════════
# 异常（视图层把它翻成 400 / 404 / 409）
# ══════════════════════════════════════════════════════════════

class SelfRunError(Exception):
    status_code = 400


class ConflictError(SelfRunError):
    status_code = 409


class NotFoundError(SelfRunError):
    status_code = 404


# ══════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════

def _f(v):
    """Decimal/None → float/None。**`None` 必须原样保留**（不许兜成 0）。"""
    return None if v is None else float(v)


def _cmp(value, line, direction):
    """按方向比较。`at_least` = 「至少」；`at_most` = 「至多」。"""
    return value >= line if direction == 'at_least' else value <= line


def get_open_stage():
    """当前进行中（或暂停中）的阶段。**同一时间只允许一个。**"""
    return SelfRunStage.objects.filter(status__in=OPEN_STAGE_STATUSES).first()


def get_closed_stages():
    return SelfRunStage.objects.filter(status='closed')


def current_period_meta(period_type='weekly'):
    """`(key, start, end)` —— **当前周期是哪一期**，与有没有阶段**无关**。

    🔴 为什么要单独给出来：前端在「还没有进行中的阶段」时也要说清
       「本周指的是哪一周」/「本月指的是哪一月」——
       否则「本周状态」与「本月状态」两页长得一模一样（分不出自己在哪一页）。
    🔴 周期标识只许**后端一把尺子**：前端按 `Date` 自己算 ISO 周，
       在跨年边界（12-29 属于下一年 W01）会**静默差一周**，而且不报错。
    """
    start, end, key = period_range(period_type, timezone.localdate())
    return key, start, end


def parse_period_key(period_type, key):
    """`'2026-W42'` / `'2026-10'` → `(start, end)`（半开区间）。"""
    try:
        if period_type == 'weekly':
            y, w = str(key).split('-W')
            mon = dt.date.fromisocalendar(int(y), int(w), 1)
            return mon, mon + dt.timedelta(days=7)
        y, m = str(key).split('-')
        first = dt.date(int(y), int(m), 1)
        return first, (first + dt.timedelta(days=32)).replace(day=1)
    except (ValueError, TypeError) as exc:
        raise SelfRunError(f'周期标识 {key!r} 不合法（周应为 2026-W42，月应为 2026-10）') from exc


# ══════════════════════════════════════════════════════════════
# 按期目标解析（🔴 全模块**唯一**一处决定「这一期的目标是多少」）
# ══════════════════════════════════════════════════════════════

def _plans_by_metric(metric_ids):
    """一次取回这些 KPI 的全部按期设定。返回 `{metric_id: [plan, ...]}`。

    ⚠️ 用「一次查询 + Python 里挑」而不是每条 KPI 查两次 ——
       8 条 KPI × 2 次 = 16 次往返，而它**每次翻页**都要跑。
    """
    out = {}
    metric_ids = [i for i in (metric_ids or []) if i]
    if not metric_ids:
        return out
    for p in SelfRunMetricPlan.objects.filter(metric_id__in=metric_ids):
        out.setdefault(p.metric_id, []).append(p)
    return out


def pick_plan(plans, period_key):
    """从一堆设定里挑出**对这一期生效**的那条。返回 `(plan, source)`。

    🔴 优先序只有这一处实现（前端不重算、不兜底）：
       ① **`single` 且恰好是这一期** ⇒ 用它（**特例压过长期**）；
       ② `from` 里 `period_key <= 本期` 的**最晚**一条 ⇒ 用它；
       ③ 都没有 ⇒ `(None, 'metric')`，回落 `SelfRunMetric` 的默认值。

    ⚠️ `period_key` 的**字符串序即时间序**：`2026-W09 < 2026-W42 < 2026-W43`，
       跨年 `2025-W52 < 2026-W01` 也成立（零填充是前提，见 `readers.week_range`）。
    """
    if not period_key:
        return None, TARGET_SOURCE_METRIC
    single = next(
        (p for p in plans if p.scope == 'single' and p.period_key == period_key), None,
    )
    if single is not None:
        return single, TARGET_SOURCE_SINGLE
    froms = [p for p in plans if p.scope == 'from' and p.period_key <= period_key]
    if froms:
        return max(froms, key=lambda p: p.period_key), TARGET_SOURCE_FROM
    return None, TARGET_SOURCE_METRIC


def resolve_targets(metric, period_key=None, plans=None):
    """这一条 KPI 在 `period_key` 这一期的**生效目标**。

    返回 `(goal, floor, source, plan)`：
    - `source` ∈ `'metric'`（阶段默认）/ `'single'`（本期特例）/ `'from'`（按期设定）；
    - `plan` = 命中的那条设定（没命中为 `None`），界面用它回答「为什么是 10h」。

    🔴 没有 `period_key`（试算 / 未落库的对象）⇒ 一律用默认值，**不猜**。
    """
    if metric.pk is None or not period_key:
        return metric.goal_value, metric.floor_value, TARGET_SOURCE_METRIC, None
    if plans is None:
        plans = list(SelfRunMetricPlan.objects.filter(metric=metric))
    plan, source = pick_plan(plans, period_key)
    if plan is None:
        return metric.goal_value, metric.floor_value, TARGET_SOURCE_METRIC, None
    return plan.goal_value, plan.floor_value, source, plan


def resolve_map(metrics, period_key):
    """批量版：`{metric_id: (goal, floor, source, plan)}`（**一次**查询）。"""
    ids = [m.id for m in metrics if m.pk]
    plans_map = _plans_by_metric(ids)
    return {
        m.id: resolve_targets(m, period_key, plans_map.get(m.id) or [])
        for m in metrics
    }


# ══════════════════════════════════════════════════════════════
# 单条读数的计算（T2 与 T3 **共用**同一段口径 —— 不许写两份）
# ══════════════════════════════════════════════════════════════

def _manual_value(metric, start, end):
    """区间内手工登记的求和（`manual` / `auto_plus_manual` 型用）。

    ⚠️ **负数 = 冲销** ⇒ 直接求和，不过滤。
    ⚠️ 未落库的 metric（试算场景）没有 id ⇒ 返回 0 而不是崩。
    """
    if not metric.pk:
        return 0.0
    agg = metric.checkins.filter(
        checkin_date__gte=start, checkin_date__lt=end,
    ).aggregate(s=Sum('value'))
    return round(float(agg['s'] or 0), 2)


def _freshness_state(metric, reader_out, goal, floor):
    """按 `constants.STALE_RULES` 判数据源新鲜度。返回 `(state, freshness_dict)`。

    ⚠️ 「有没有设线」判的是**这一期生效的目标**（`goal` / `floor`），
       不是 `metric.goal_value` —— 否则「本期特例把两条都留空」会被算成「已配置」。
    """
    kind = (metric.source_config or {}).get('kind')
    rule = STALE_RULES.get(kind)
    at = reader_out.get('freshness_at')
    fresh = {'kind': kind, 'at': at.isoformat() if hasattr(at, 'isoformat') else None}

    if goal is None and floor is None:
        return 'unconfigured', fresh          # 没设线 ⇒ 只展示不判定

    if rule is None:
        return 'ok', fresh                    # 手工型没有新鲜度概念

    if at is None:
        # 源表**从来没有过数据** —— 这不是「过期」，是「确实没有」。
        # `stale` 的语义是「该更新却没更新」；空表是「就没开始过」⇒ 按 0 处理（判 empty）。
        return 'ok', fresh

    # 🔴 「哪一天」按**本地日**算：`Max('<datetime 列>')` 回来的是 aware datetime，
    #    直接 `.date()` 拿的是 **UTC 日** —— 本地 00:00–08:00 记的那条会被算成「昨天」，
    #    在 3 天 / 7 天这种紧阈值上刚好能把「昨天记的」判成 `stale`。
    if isinstance(at, dt.datetime):
        at_date = timezone.localtime(at).date() if timezone.is_aware(at) else at.date()
    else:
        at_date = at
    days = (timezone.localdate() - at_date).days
    fresh.update({'days': days, 'limit': rule['days'], 'hint': rule['hint']})
    if days > rule['days']:
        return 'stale', fresh
    return 'ok', fresh


def evaluate_verdict(final, state, source_count, goal, floor, direction):
    """单条 KPI 的本期判定（设计稿 §11.1）。

    🔴 分支顺序是**刻意的**：
       ① `unknown`（系统不知道）→ 不进分母；
       ② `empty`（系统正常、源里一条都没有）→ **进分母**（「真的没做」要算账）；
       ③ 有数 ⇒ 按 `goal` / `floor` 判。

    ⚠️ `goal` / `floor` 是**这一期生效的**目标（可能来自按期设定），
       不是 `metric.goal_value` —— 判定必须与读数里显示的那两个数**同一份**，
       否则会出现「显示的是一套、判的是另一套」。
    """
    if state in ('stale', 'unconfigured'):
        return 'unknown'
    if final is None:
        return 'unknown'
    if source_count == 0 and final == 0:
        return 'empty'

    goal, floor = _f(goal), _f(floor)
    if floor is not None:
        if not _cmp(final, floor, direction):
            return 'miss'
        if goal is not None and _cmp(final, goal, direction):
            return 'goal'
        return 'floor'
    if goal is not None:
        return 'goal' if _cmp(final, goal, direction) else 'miss'
    return 'unknown'


def compute_metric_reading(metric, start, end, skipped=False, period_key=None, plans=None):
    """算一条 KPI 在 `[start, end)` 上的完整读数。

    返回的 dict **同时用于 T2 展示与 T3 冻结** —— 口径只有这一份实现。

    🔴 `period_key` 决定「这一期的目标」取自哪里（默认值 / 本期特例 / 按期设定）：
       - 传了 ⇒ 按 `resolve_targets` 解析，并在读数里带上 `target_source`；
       - 没传（试算等）⇒ 用 `metric` 的默认值。
       ⚠️ **冻结进 `Period.readings` 的是解析后的值** ⇒ 归档之后
          「这一期的目标是多少」**永远能回答**，不受此后任何修订影响。
    """
    out = run_reader(metric, start, end)
    goal, floor, target_source, plan = resolve_targets(metric, period_key, plans)
    state, fresh = _freshness_state(metric, out, goal, floor)
    reader_value = out['value']
    reader_count = out['count']

    # ── 三数合并（设计稿 §4.1 的表）──────────────────────────
    if metric.source_kind == 'manual':
        auto_value, manual_value = None, reader_value
        final_value = manual_value
        source_count = reader_count
    elif metric.source_kind == 'auto':
        auto_value, manual_value = reader_value, None
        final_value = auto_value
        source_count = reader_count
    else:  # auto_plus_manual：reader 给自动部分，另加手工补记
        auto_value = reader_value
        manual_value = _manual_value(metric, start, end)
        final_value = None if auto_value is None else round(auto_value + manual_value, 2)
        source_count = reader_count

    verdict = evaluate_verdict(final_value, state, source_count, goal, floor, metric.direction)

    return {
        'metric_id': metric.id,
        'name': metric.name,
        'unit': metric.unit,
        'direction': metric.direction,
        'period_type': metric.period_type,
        'agg': metric.agg,
        'source_kind': metric.source_kind,
        'goal_value': _f(goal),
        'floor_value': _f(floor),
        # 🔴 「为什么是这个数」也取**生效那一份**的依据：
        #    本期特例有自己写的依据就用它，没有才落回阶段默认的。
        'goal_why': (plan.goal_why if plan and plan.goal_why else metric.goal_why),
        'floor_why': (plan.floor_why if plan and plan.floor_why else metric.floor_why),
        # 🔴 目标来自哪：`metric` 默认 / `single` 本期特例 / `from` 按期设定。
        #    三者必须能分辨 —— 全都显示成同一个数的话，
        #    「我这周的目标怎么变了」就永远说不清（而界面两处都「看着正常」）。
        'target_source': target_source,
        'target_source_label': TARGET_SOURCE_LABELS.get(target_source, ''),
        'plan_id': plan.id if plan else None,
        'plan_scope': plan.scope if plan else None,
        'plan_note': (plan.note if plan else '') or '',
        # 🔴 三个数都要在：只存 final 的话，三个月后没法回答「这 1 天是自动取的还是你补的」
        'auto_value': auto_value,
        'manual_value': manual_value,
        'final_value': final_value,
        'verdict': verdict,
        'state': state,
        'skipped': skipped,
        # 溯源（V2：让你看见尺子）
        'breakdown': out['breakdown'][:50],
        'breakdown_total': len(out['breakdown']),
        'warnings': out['warnings'] + out.get('issues', []),
        'freshness': fresh,
    }


# ══════════════════════════════════════════════════════════════
# 判定引擎
# ══════════════════════════════════════════════════════════════

def compute_period_status(stage, readings):
    """周/月判定（设计稿 §5.4）。

    🔴 分母口径：
       - `unknown`（含 `stale` / `unconfigured`）**不进分母**（V1：「没记」不是「没做」）；
       - `skipped`（本周明确说不算）**不进分母**；
       - `empty`（系统正常、真的一条没有）**进分母** —— 它才是「真的没做」。
    🔴 分子 = `goal` 或 `floor`（**达底线即算达标**，与 §3.3 试算的「达标 7/11」同一把尺子）。
    """
    if stage.status == 'paused':
        return 'fallow'
    counted = [r for r in readings if r['verdict'] != 'unknown' and not r.get('skipped')]
    if not counted:
        return 'no_record'
    ok = sum(1 for r in counted if r['verdict'] in ('goal', 'floor'))
    ratio = ok / len(counted)
    for name, lower in PERIOD_VERDICT_BANDS:
        if ratio >= lower:
            return name
    return 'slid'


def compute_monthly_status(answer_sheet):
    """月度判定：按三问里答「是」的个数。

    🔴 `answer=None`（**还没答**）与 `answer=False`（**答了否**）必须分开 ——
       又是一处 `null ≠ 0`。只数 `is True` 的。
    """
    if not answer_sheet:
        return ''
    yes = 0
    for key in ('q1_income', 'q2_output', 'q3_runway'):
        item = answer_sheet.get(key) or {}
        if item.get('answer') is True:
            yes += 1
    return MONTHLY_QUESTION_BANDS.get(yes, '')


# ══════════════════════════════════════════════════════════════
# T1 · 制定配置
# ══════════════════════════════════════════════════════════════

def _template_fields(tpl):
    """`SelfRunTemplate` → 建阶段时用来兜底的字段字典（与旧常量的键**同名**）。"""
    return {
        'name': tpl.name, 'period_type': tpl.period_type, 'unit': tpl.unit,
        'direction': tpl.direction, 'goal_value': tpl.goal_value,
        'floor_value': tpl.floor_value, 'goal_why': tpl.goal_why,
        'floor_why': tpl.floor_why, 'agg': tpl.agg,
        'source_kind': tpl.source_kind, 'source_config': tpl.source_config,
        'sort_order': tpl.sort_order,
    }


def find_template(key):
    """按 `key` 取一条模板。没有 ⇒ `None`（**不报错**：来源只是展示用的标记）。"""
    if not key:
        return None
    return SelfRunTemplate.objects.filter(key=key).first()


def list_l2_options():
    """可选的活动类型（= `temporal_task_meta.activity_type` 的去重值）。

    🔴 取自**库**不是常量表：常量表只是「出生证」，库里那行才是真源
       （`readers._temporal_filtered` 的口径也一样）。
    给模板编辑界面用 —— 让 `temporal_hours` 的 `l2` 过滤可以**选**而不是手打，
       手打的错字不报错、只会静默取到 0。
    """
    from apps.temporal.models import TaskMeta
    return sorted({
        v for v in TaskMeta.objects.values_list('activity_type', flat=True) if v
    })


def list_templates(period_type=None):
    """模板库 —— 🔴 读**表**（不再读 `templates.py` 常量）。

    常量只在迁移 `0002` 里被 seed 一次；此后模板的增删改一律落库
    ⇒ 你在界面上删掉的模板**不会**在下次启动时自己回来。
    """
    qs = SelfRunTemplate.objects.all()
    if period_type:
        qs = qs.filter(period_type=period_type)
    # 「被几个 KPI 引用过」一次聚合算完（模板与阶段只靠字符 key 关联，没法 annotate）
    used = dict(
        SelfRunMetric.objects.exclude(template_key='')
        .values_list('template_key').annotate(n=Count('id'))
    )
    out = []
    for t in qs:
        kind = (t.source_config or {}).get('kind')
        row = _template_fields(t)
        row.update({
            'id': t.id,
            'key': t.key,
            'reader_kind': kind,
            'reader_hint': (STALE_RULES.get(kind) or {}).get('hint', ''),
            'used_count': used.get(t.key, 0),
        })
        out.append(row)
    return out


def _validate_lines(goal, floor, direction, label):
    """目标与底线的方向性校验（**模板 / 按期设定共用**）。错就报，不静默纠正。"""
    if goal is not None and floor is not None:
        g, f = float(goal), float(floor)
        if direction == 'at_least' and g < f:
            raise SelfRunError(f'{label}：目标 {g} 低于底线 {f}，请确认。')
        if direction == 'at_most' and g > f:
            raise SelfRunError(f'{label}：目标 {g} 高于底线 {f}（方向为「至多」），请确认。')


def _validate_source_config(source_kind, source_config, label):
    """校验「取数方式 + 取数器」能不能真的跑起来，并**归一化** `kind`。

    🔴 为什么要在**建模板**的时候就报错：未知 `kind` 要到**取数那一刻**才炸
       （`run_reader` 直接抛 `ValueError`）⇒ 表现是「阶段建好了、某一页 500」。
       早报一格，错误就落在「你刚点的那个按钮」上，而不是三天后的某一页。
    🔴 `source_kind='manual'` 也**必须**有一个注册表内的 `kind`：手工项的取值走
       `run_reader`（只是结果被当作 `manual_value`）⇒ `kind` 空着照样会炸。
       没给就默认 `manual_sum`。
    """
    cfg = dict(source_config or {})
    kind = cfg.get('kind') or ('manual_sum' if source_kind == 'manual' else None)
    if kind not in READER_KEYS:
        raise SelfRunError(
            f'{label}：取数方式要配一个取数器，而 {kind!r} 不在允许清单里（{list(READER_KEYS)}）。'
        )
    if kind == 'module_value':
        key = (cfg.get('where') or {}).get('key')
        if key not in MODULE_VALUE_WHITELIST:
            raise SelfRunError(
                f'{label}：`module_value` 的键 {key!r} 不在白名单内'
                f'（{list(MODULE_VALUE_WHITELIST)}）。'
            )
    cfg['kind'] = kind
    return cfg


_TEMPLATE_EDITABLE = (
    'name', 'period_type', 'unit', 'direction', 'goal_value', 'floor_value',
    'goal_why', 'floor_why', 'agg', 'source_kind', 'source_config', 'sort_order',
)


@transaction.atomic
def create_template(payload):
    """新建一条自定义模板。

    🔴 `key` **由后端生成**（`custom_<8位>`），前端不许自己编 ——
       它是显示层与 seed 数据之间的稳定标识，撞了就是「来源指向别人的模板」。
    """
    name = (payload.get('name') or '').strip()
    if not name:
        raise SelfRunError('模板名称不能为空。')
    period_type = payload.get('period_type') or 'weekly'
    if period_type not in ('weekly', 'monthly'):
        raise SelfRunError(f'未知周期类型：{period_type!r}')
    direction = payload.get('direction') or 'at_least'
    _validate_lines(
        payload.get('goal_value'), payload.get('floor_value'), direction, f'模板「{name}」',
    )
    source_kind = payload.get('source_kind') or 'manual'
    source_config = _validate_source_config(
        source_kind, payload.get('source_config'), f'模板「{name}」',
    )

    key = ''
    for _ in range(5):
        candidate = 'custom_' + uuid.uuid4().hex[:8]
        if not SelfRunTemplate.objects.filter(key=candidate).exists():
            key = candidate
            break
    if not key:
        raise SelfRunError('生成模板标识失败，请重试。')

    sort_order = payload.get('sort_order')
    if sort_order is None:
        last = SelfRunTemplate.objects.order_by('-sort_order').first()
        sort_order = ((last.sort_order or 0) + 10) if last else 10

    return SelfRunTemplate.objects.create(
        key=key, name=name, period_type=period_type,
        unit=payload.get('unit') or '',
        direction=direction,
        goal_value=payload.get('goal_value'),
        floor_value=payload.get('floor_value'),
        goal_why=payload.get('goal_why') or '',
        floor_why=payload.get('floor_why') or '',
        agg=payload.get('agg') or 'manual_sum',
        source_kind=source_kind,
        source_config=source_config,
        sort_order=sort_order,
    )


@transaction.atomic
def update_template(tpl, payload):
    """改模板。**`key` 不可改**（它是 `SelfRunMetric.template_key` 的指向）。"""
    data = {k: v for k, v in (payload or {}).items() if k in _TEMPLATE_EDITABLE}
    if 'name' in data and not (data['name'] or '').strip():
        raise SelfRunError('模板名称不能为空。')
    label = f'模板「{data.get("name") or tpl.name}」'
    goal = data.get('goal_value', tpl.goal_value)
    floor = data.get('floor_value', tpl.floor_value)
    direction = data.get('direction') or tpl.direction
    _validate_lines(goal, floor, direction, label)
    # 只在**动过取数相关字段**时校验（否则每次改名都等于重跑一遍取数器校验，
    # 而老模板里可能正躺着一个当年合法、如今被移出白名单的 kind）
    if 'source_kind' in data or 'source_config' in data:
        data['source_config'] = _validate_source_config(
            data.get('source_kind') or tpl.source_kind,
            data.get('source_config', tpl.source_config),
            label,
        )

    changed = []
    for k, v in data.items():
        if getattr(tpl, k) == v:
            continue
        setattr(tpl, k, v)
        changed.append(k)
    if changed:
        tpl.save(update_fields=changed + ['updated_at'])
    return tpl, changed


@transaction.atomic
def delete_template(tpl):
    """删模板。

    🔴 **不影响任何已建阶段** —— `SelfRunMetric.template_key` 只是字符标记、不是 FK，
       所以不会触发 `PROTECT`，也不会连带删掉任何 KPI 或读数。
       代价只是那些 KPI 的「来源」失去指向（来源只用于展示，不参与取数）。
    返回**曾被引用过的 KPI 条数**，供界面在删除前告诉你影响面。
    """
    used = SelfRunMetric.objects.filter(template_key=tpl.key).count()
    tpl.delete()
    return used


def preview_metric(payload, periods: int = 11):
    """**纯试算，绝不落库**（你可以放心点一百次）。

    给定一份「还没建」的 KPI 配置，算出它在最近 N 个已过去周期上的读数分布，
    并给出「若底线设成 X，过去会有几期达标」。

    ⚠️ 这里构造的 `SelfRunMetric` **不 save** —— `manual_sum` reader 对无 pk 的对象
       返回 0（不崩），其余 reader 全部只读源表。
    """
    period_type = payload.get('period_type') or 'weekly'
    if period_type not in ('weekly', 'monthly'):
        raise SelfRunError(f'未知周期类型：{period_type!r}')

    probe = SelfRunMetric(
        stage_id=0,
        name=payload.get('name') or '试算',
        period_type=period_type,
        unit=payload.get('unit') or '',
        direction=payload.get('direction') or 'at_least',
        agg=payload.get('agg') or 'sum_hours',
        source_kind=payload.get('source_kind') or 'auto',
        source_config=payload.get('source_config') or {},
        goal_value=payload.get('goal_value'),
        floor_value=payload.get('floor_value'),
    )

    today = timezone.localdate()
    rows = []
    latest_warnings = []
    for i in range(1, periods + 1):
        if period_type == 'weekly':
            ref = today - dt.timedelta(days=7 * i)
        else:
            ref = (today.replace(day=1) - dt.timedelta(days=1))
            for _ in range(i):
                ref = (ref.replace(day=1) - dt.timedelta(days=1))
        start, end, key = period_range(period_type, ref)
        r = compute_metric_reading(probe, start, end)
        if i == 1:
            latest_warnings = r['warnings']      # 最近一期的告警（越界值 / 两把尺子…）
        rows.append({'key': key, 'start': str(start), 'end': str(end),
                     'value': r['final_value'], 'state': r['state'], 'verdict': r['verdict']})
    rows.reverse()

    values = [r['value'] for r in rows if r['value'] is not None]
    stats = {}
    if values:
        s = sorted(values)
        stats = {
            'count': len(values),
            'min': min(values), 'max': max(values),
            'median': s[len(s) // 2] if len(s) % 2 else round((s[len(s) // 2 - 1] + s[len(s) // 2]) / 2, 2),
            'mean': round(sum(values) / len(values), 2),
        }

    # 「底线设成 X 会有几期达标」—— 按达底线即算达标，与周期判定同一把尺子
    floor_options = payload.get('floor_options') or [3, 5, 9, 12]
    hit = [
        {
            'floor': opt,
            'hit': sum(1 for v in values if _cmp(v, opt, probe.direction)),
            'total': len(values),
        }
        for opt in floor_options
    ]

    return {
        'period_type': period_type,
        'rows': rows,
        'stats': stats,
        'floor_options': hit,
        'reader_kind': probe.source_config.get('kind'),
        'warnings': latest_warnings,
    }


def _validate_metric_payload(m, index, template):
    """校验一条 KPI 配置。**错就报，不静默纠正。**

    ⚠️ 校验的是**最终生效值**（不传 ⇒ 模板默认），而不是「这次请求里传了什么」——
       否则「模板 12/5 但请求里只传了 goal=3」这种情况会绕过校验。
    """
    goal = m.get('goal_value', template.get('goal_value'))
    floor = m.get('floor_value', template.get('floor_value'))
    direction = m.get('direction') or template.get('direction') or 'at_least'
    label = f'第 {index} 条「{m.get("name") or template.get("name") or "KPI"}」'
    _validate_lines(goal, floor, direction, label)
    return direction


@transaction.atomic
def create_stage(payload):
    """T1 唯一的写库动作（设计稿 §3.4）：**一个事务里写 3 张表**。

    ⇒ `Stage`（一步到位 `status='active'`，不留 draft 残留）
      + `Metric × N`
      + `MetricLog × N`（`created` —— 「创建」也是「一次配置变更」）
    """
    metrics_in = payload.get('metrics') or []
    if not metrics_in:
        raise SelfRunError('至少要有一条 KPI 才能开始。')
    if SelfRunStage.objects.filter(status__in=OPEN_STAGE_STATUSES).exists():
        existing = SelfRunStage.objects.filter(status__in=OPEN_STAGE_STATUSES).first()
        raise SelfRunError(
            f'已有进行中的阶段「{existing.name}」，请先收尾它再开启新的。'
        )

    name = (payload.get('name') or '').strip()
    if not name:
        raise SelfRunError('阶段名称不能为空。')
    start_date = payload.get('start_date') or timezone.localdate()
    end_date = payload.get('end_date')
    if end_date and end_date < start_date:
        raise SelfRunError('终点不能早于起点。')

    stage = SelfRunStage.objects.create(
        name=name, start_date=start_date, end_date=end_date,
        status='active', note=payload.get('note') or '',
    )

    created = []
    for i, m in enumerate(metrics_in, start=1):
        # 🔴 模板现在读**表**（可自定义）。查不到就当作「没有模板」——
        #    不报错：请求里本来就可能带全字段（向导会把模板值抄进请求），
        #    而 `template_key` 只是「来源」标记，不参与取数。
        tpl = find_template(m.get('template_key') or '')
        template = _template_fields(tpl) if tpl else {}
        direction = _validate_metric_payload(m, i, template)
        metric = SelfRunMetric.objects.create(
            stage=stage,
            template_key=m.get('template_key') or '',
            name=m.get('name') or template.get('name') or f'KPI {i}',
            period_type=m.get('period_type') or template.get('period_type') or 'weekly',
            unit=m.get('unit') or template.get('unit') or '',
            direction=direction,
            # 🔴 数值字段必须用 `.get(k, default)` —— **不能用 `or`**：
            #    `0` 是合法的目标值（「本月 0 次」是真实诉求），`or` 会把它换成模板值。
            #    ⚠️ 且「不传」≠「传 null」：不传 ⇒ 取模板默认；传 null ⇒ 就是要「没有这一档」。
            goal_value=m.get('goal_value', template.get('goal_value')),
            floor_value=m.get('floor_value', template.get('floor_value')),
            goal_why=m.get('goal_why') or template.get('goal_why') or '',
            floor_why=m.get('floor_why') or template.get('floor_why') or '',
            agg=m.get('agg') or template.get('agg') or 'sum_hours',
            source_kind=m.get('source_kind') or template.get('source_kind') or 'auto',
            source_config=m.get('source_config') or template.get('source_config') or {},
            status='active',
            sort_order=m.get('sort_order', template.get('sort_order') or i * 10),
        )
        SelfRunMetricLog.objects.create(
            metric=metric, action='created', reason='template_use',
            to_value={
                'name': metric.name, 'period_type': metric.period_type,
                'unit': metric.unit, 'direction': metric.direction,
                'goal_value': _f(metric.goal_value), 'floor_value': _f(metric.floor_value),
                'agg': metric.agg, 'source_kind': metric.source_kind,
                'source_config': metric.source_config,
            },
        )
        created.append(metric)

    return stage, created


# ══════════════════════════════════════════════════════════════
# T1b · 按期修订（「每周/每月修订下一周、月」）
# ══════════════════════════════════════════════════════════════

def _shift_period(period_type, today, offset):
    """`today` 前/后挪 `offset` 期。

    ⚠️ 月要按**日历加法**（`2026-01-31` 的下一月是 `2026-02-01` 那一期），
       不能用「+30 天」—— 那会在 2 月与 12 月静默错位。
    """
    if period_type == 'weekly':
        return today + dt.timedelta(days=7 * offset)
    total = (today.year * 12 + today.month - 1) + offset
    return dt.date(total // 12, total % 12 + 1, 1)


def list_period_options(period_type, count=6):
    """「哪几期可以修订」—— 上一期 + 本期 + 未来 `count` 期。

    🔴 周期标识只许**后端一把尺子**：前端拿 `Date` 自己算 ISO 周，
       在跨年边界（12-29 属于下一年 W01）会**静默差一周**，而且不报错。
    """
    if period_type not in ('weekly', 'monthly'):
        raise SelfRunError(f'未知周期类型：{period_type!r}')
    today = timezone.localdate()
    out = []
    for offset in range(-1, count):
        start, end, key = period_range(period_type, _shift_period(period_type, today, offset))
        out.append({
            'key': key,
            'start': str(start),
            'end': str(end),
            'offset': offset,
            'label': '上一期' if offset < 0 else ('本期' if offset == 0 else f'往后第 {offset} 期'),
        })
    return out


def list_targets(period_type, period_key, stage=None):
    """某一期「全套 KPI 的**生效目标**」—— 修订界面念的就是它。

    🔴 与 `get_current_period` 的分工：那个要**跑 7 个取数器**算读数，
       这个只回答「这一期的目标是多少」—— 修订界面不该顺带把取数也跑一遍。
       两者共用**同一份** `resolve_targets`，不写第二份口径。
    """
    stage = stage or get_open_stage()
    if stage is None:
        return None
    start, end = parse_period_key(period_type, period_key)
    metrics = [m for m in stage.metrics.filter(status='active')
               if m.period_type == period_type]
    plans_map = _plans_by_metric([m.id for m in metrics])
    rows = []
    for m in metrics:
        plans = plans_map.get(m.id) or []
        goal, floor, source, plan = resolve_targets(m, period_key, plans)
        rows.append({
            'metric_id': m.id,
            'name': m.name,
            'unit': m.unit,
            'direction': m.direction,
            'base_goal': _f(m.goal_value),
            'base_floor': _f(m.floor_value),
            'goal_value': _f(goal),
            'floor_value': _f(floor),
            'target_source': source,
            'target_source_label': TARGET_SOURCE_LABELS.get(source, ''),
            'goal_why': (plan.goal_why if plan and plan.goal_why else m.goal_why),
            'floor_why': (plan.floor_why if plan and plan.floor_why else m.floor_why),
            'plan_id': plan.id if plan else None,
            'plan_scope': plan.scope if plan else None,
            'plan_note': (plan.note if plan else '') or '',
            'plan_count': len(plans),
        })
    cur_key = current_period_meta(period_type)[0]
    return {
        'stage': stage,
        'period_type': period_type,
        'period_key': period_key,
        'period_start': str(start),
        'period_end': str(end),
        'current_key': cur_key,
        'is_current': period_key == cur_key,
        # ⚠️ 过去的期**能改**（改的是「当时该拿什么尺子」，且留痕），
        #    但界面要说清它已经过去 —— 只有**已归档**的期才会被闸门拦住（409）。
        'is_past': period_key < cur_key,
        'rows': rows,
    }


@transaction.atomic
def set_plan(metric, period_key, scope, goal_value, floor_value,
             goal_why='', floor_why='', note=''):
    """设定某一条 KPI 在**某一期**的目标（「修订下一周/月」的唯一写口）。

    🔴 归档闸门：落在**已归档周期**里 ⇒ **409** —— 与「补记」同一条规则
       （归档 = 定格，之后改目标会让读数里显示的值与结论里判的值**无声分家**）。
    🔴 `scope='from'` 会**一直生效到出现更晚的 `from`** —— 这一点必须在界面上说清，
       否则你会以为它只是「把这一期改了」。
    🔴 每次设定都写 `MetricLog`（`action='plan_changed'`）⇒ T4 的时间轴上看得见
       「哪一期换过尺子」。
    """
    scope = scope or 'single'
    if scope not in ('single', 'from'):
        raise SelfRunError(f'未知的作用域 {scope!r}（只能是 single / from）。')
    if metric.status != 'active':
        raise SelfRunError(f'「{metric.name}」已退役，先恢复它再设定目标。')
    # 顺带校验格式**与周期类型是否匹配**（周 key 送给月度 KPI 会在这里报错）
    start, _end = parse_period_key(metric.period_type, period_key)
    _assert_period_open(metric, start)
    _validate_lines(goal_value, floor_value, metric.direction, f'「{metric.name}」{period_key}')

    before = SelfRunMetricPlan.objects.filter(
        metric=metric, period_key=period_key, scope=scope,
    ).first()
    plan, _created = SelfRunMetricPlan.objects.update_or_create(
        metric=metric, period_key=period_key, scope=scope,
        defaults={
            'goal_value': goal_value, 'floor_value': floor_value,
            'goal_why': goal_why or '', 'floor_why': floor_why or '', 'note': note or '',
        },
    )
    log = SelfRunMetricLog.objects.create(
        metric=metric, action='plan_changed',
        field_name=f'{scope}:{period_key}'[:30],
        from_value=(None if before is None else {
            'goal_value': _f(before.goal_value), 'floor_value': _f(before.floor_value),
        }),
        to_value={'goal_value': _f(plan.goal_value), 'floor_value': _f(plan.floor_value)},
        reason_note=note or '',
    )
    return plan, log


@transaction.atomic
def delete_plan(plan):
    """取消某一期的设定（回到上一层口径：`single` 删掉 ⇒ 落回 `from` 或默认值）。

    ⚠️ 这里**真的是删除**，不是「冲销」—— `Plan` 是**配置**不是流水
       （流水才适用项目铁律「撤销 ≠ 删除」）。留痕由 `MetricLog` 承担。
    ⚠️ 同样受归档闸门约束：已归档的期不许动。
    """
    metric = plan.metric
    start, _end = parse_period_key(metric.period_type, plan.period_key)
    _assert_period_open(metric, start)
    info = {
        'period_key': plan.period_key, 'scope': plan.scope,
        'goal_value': _f(plan.goal_value), 'floor_value': _f(plan.floor_value),
    }
    plan.delete()
    log = SelfRunMetricLog.objects.create(
        metric=metric, action='plan_changed',
        field_name=f'{info["scope"]}:{info["period_key"]}'[:30],
        from_value=info, to_value=None,
        reason_note='取消了这一期的设定',
    )
    return metric, log


# ══════════════════════════════════════════════════════════════
# T2 · 执行
# ══════════════════════════════════════════════════════════════

def _find_current_period(stage, period_type):
    """查当期 `Period` 行。**查不到返回 `None`（不建行）。**"""
    start, end, key = period_range(period_type, timezone.localdate())
    obj = SelfRunPeriod.objects.filter(
        stage=stage, period_type=period_type, period_key=key,
    ).first()
    return obj, start, end, key


def get_current_period(period_type='weekly'):
    """「本周/本月状态」。

    🔴 **GET 不写库**（设计稿 §2.3）：
       - 当期已有行 ⇒ 返回它（若已归档 ⇒ **直接读快照，绝不重算**）；
       - 当期没有行 ⇒ 返回**虚拟对象**（`id=None`），首次写入时才建行。

    为什么不能 `get_or_create`：GET 写库 = 你翻个页就产生一行数据，
    且并发下会撞 `unique_together`。
    """
    stage = get_open_stage()
    if stage is None:
        return None, None

    obj, start, end, key = _find_current_period(stage, period_type)

    if obj is not None and obj.closed_at is not None:
        # 🔴 已归档 ⇒ 读冻结快照。**不重算** —— 否则等于没归档。
        return obj, {'source': 'snapshot', 'period_key': key, 'start': start, 'end': end}

    skipped = list(obj.skipped_metric_ids or []) if obj else []
    metrics = [m for m in stage.metrics.filter(status='active')
               if m.period_type == period_type]
    # 🔴 按期设定**一次取回**（别在循环里逐条查），再由 `compute_metric_reading` 解析 ——
    #    「这一期的目标是多少」只有 `resolve_targets` 一处实现。
    plans_map = _plans_by_metric([m.id for m in metrics])
    readings = [
        compute_metric_reading(
            m, start, end, skipped=m.id in skipped,
            period_key=key, plans=plans_map.get(m.id) or [],
        )
        for m in metrics
    ]

    if obj is None:
        obj = SelfRunPeriod(
            stage=stage, period_type=period_type, period_key=key,
            period_start=start, period_end=end,
            is_partial=start < stage.start_date,
            status='',
        )
        obj.pk = None
    obj.readings = readings
    return obj, {'source': 'live', 'period_key': key, 'start': start, 'end': end}


def _assert_period_open(metric, day):
    """🔴 落在**已归档周期**里的登记一律拒绝（409），**不静默接受**。

    为什么必须拦住：归档 = 定格 —— `Period.readings` 是那一刻算出来冻住的，
    之后再补记**不会**、也不该回头改它。
    ⇒ 静默接受这笔登记 = 明细账里有一笔、结论里没有，两边**悄悄分家**，
      而界面上两处都「看着正常」。

    出口写在错误文案里：要么先「重开这一期」（留痕），要么记到当前周期。
    """
    _, _, key = period_range(metric.period_type, day)
    closed = SelfRunPeriod.objects.filter(
        stage_id=metric.stage_id, period_type=metric.period_type,
        period_key=key, closed_at__isnull=False,
    ).first()
    if closed is None:
        return
    raise ConflictError(
        f'{key} 已经归档定格了（{timezone.localtime(closed.closed_at):%Y-%m-%d}）—— '
        f'那一期的结论不会因为这笔登记而改变。'
        f'要么先「重开这一期」（会留痕），要么把这笔记到当前周期。'
    )


def create_checkin(metric, checkin_date, value, note=''):
    """手工登记。

    🔴 `source_kind='auto'` 的条目**没有补记入口** —— 自动取错了要去改源
       （「一个写口」原则），不是在这里覆盖。
    🔴 落在已归档周期里的登记 **409**（见 `_assert_period_open`）。
    """
    if metric.source_kind == 'auto':
        raise SelfRunError(f'「{metric.name}」是自动取数项，没有补记入口（自动取错了请去改数据源）。')
    v = float(value)
    if metric.source_kind == 'auto_plus_manual' and v < 0:
        raise SelfRunError('补记不能填负数 —— 要撤销请用「撤销这一笔」。')
    day = checkin_date or timezone.localdate()
    _assert_period_open(metric, day)
    return SelfRunCheckin.objects.create(
        metric=metric, checkin_date=day, value=v, note=note or '',
    )


def reverse_checkin(checkin):
    """撤销 = **补一条负值**（项目铁律：撤销 ≠ 删除）。

    一条记录**最多被冲销一次**（再冲销就重复扣了）。
    🔴 同样受归档闸门约束 —— 冲销也是一笔新流水，落在已归档周期里就 409。
    """
    if float(checkin.value) < 0:
        raise SelfRunError('这已经是一条冲销记录了。')
    exists = SelfRunCheckin.objects.filter(
        metric=checkin.metric, note=f'冲销 #{checkin.id}',
    ).exists()
    if exists:
        raise ConflictError('这一笔已经冲销过了，不能重复冲销。')
    _assert_period_open(checkin.metric, checkin.checkin_date)
    return SelfRunCheckin.objects.create(
        metric=checkin.metric, checkin_date=checkin.checkin_date,
        value=-float(checkin.value), note=f'冲销 #{checkin.id}',
    )


@transaction.atomic
def update_metric(metric, data, reason=None, reason_note=''):
    """改 KPI 配置（goal / floor / source_config / …）。

    🔴 **不新建 Metric 行** —— `metric_id` 必须稳定，否则 `Period.readings` 里的引用会失效。
    🔴 **每次改都写 `MetricLog`**，且**必须问原因**（校准 or 状态）——
       系统不判断对错，只记录；三个月后你在时间轴上自己看得出来。
    """
    tracked = ('goal_value', 'floor_value', 'source_config', 'agg', 'direction',
               'name', 'unit', 'sort_order')
    logs = []
    for field in tracked:
        if field not in data:
            continue
        old = getattr(metric, field)
        new = data[field]
        if field in ('goal_value', 'floor_value'):
            old, new = _f(old), _f(new)
        if old == new:
            continue
        action = {
            'goal_value': 'goal_changed',
            'floor_value': 'floor_changed',
        }.get(field, 'config_changed')
        setattr(metric, field, new)
        logs.append(SelfRunMetricLog(
            metric=metric, action=action, field_name=field,
            from_value=old, to_value=new,
            reason=reason, reason_note=reason_note or '',
        ))
    if not logs:
        return metric, []
    metric.save()
    # ⚠️ 逐个 `save()`，不用 `bulk_create` —— 后者**不会跑 `pre_save`**，
    #    `auto_now_add` 与 `JSONField` 的序列化都会缺，落库后 `from_value` 变 NULL。
    for log in logs:
        log.save()
    return metric, logs


def retire_metric(metric, reason_note=''):
    """退役（「这条我不要了」）。

    ⚠️ 与两种「暂停」**作用域不同**（设计稿 §2.3）：
       「这周这条先不算」→ `Period.skipped_metric_ids`；
       「整个阶段歇一阵」→ `Stage.status='paused'`。
    """
    if metric.status == 'retired':
        return metric, None
    metric.status = 'retired'
    metric.save(update_fields=['status', 'updated_at'])
    log = SelfRunMetricLog.objects.create(
        metric=metric, action='retired', field_name='status',
        from_value='active', to_value='retired', reason_note=reason_note or '',
    )
    return metric, log


def revive_metric(metric, reason_note=''):
    if metric.status == 'active':
        return metric, None
    metric.status = 'active'
    metric.save(update_fields=['status', 'updated_at'])
    log = SelfRunMetricLog.objects.create(
        metric=metric, action='revived', field_name='status',
        from_value='retired', to_value='active', reason_note=reason_note or '',
    )
    return metric, log


def pause_stage(stage, reason=None, resume_at=None, note=''):
    """整个阶段暂停（休耕）。字段命名对齐 `redemption.RedemptionPeriod` 的既有先例。"""
    if stage.status not in OPEN_STAGE_STATUSES:
        raise SelfRunError(f'阶段当前是「{stage.get_status_display()}」，不能暂停。')
    stage.status = 'paused'
    stage.pause_reason = reason or 'other'
    stage.paused_since = timezone.localdate()
    stage.resume_at = resume_at
    if note:
        stage.note = note
    stage.save(update_fields=[
        'status', 'pause_reason', 'paused_since', 'resume_at', 'note', 'updated_at',
    ])
    return stage


def resume_stage(stage):
    if stage.status != 'paused':
        raise SelfRunError('阶段当前不是暂停中。')
    stage.status = 'active'
    stage.pause_reason = None
    stage.paused_since = None
    stage.resume_at = None
    stage.save(update_fields=[
        'status', 'pause_reason', 'paused_since', 'resume_at', 'updated_at',
    ])
    return stage


def heartbeat(seen=True):
    """「回访即握手」（V3：不追着你跑）。

    🔴 **只 UPDATE `last_seen_at`** —— 不判好坏、不改任何 KPI、不建记录。
    🔴 同一天最多写一次。
    """
    stage = get_open_stage()
    if stage is None:
        return None, False
    today = timezone.localdate()
    if stage.last_seen_at and timezone.localtime(stage.last_seen_at).date() == today:
        return stage, False
    stage.last_seen_at = timezone.now()
    stage.save(update_fields=['last_seen_at', 'updated_at'])
    return stage, True


def heartbeat_state(stage):
    """算「已经 N 天没在这里见到你」—— 中性文案，不是红色告警。"""
    if stage is None or stage.last_seen_at is None:
        return {'last_seen_at': None, 'days': None, 'message': None}
    days = (timezone.localdate() - timezone.localtime(stage.last_seen_at).date()).days
    message = None
    if days >= 3:
        message = f'已经 {days} 天没在这里见到你了'
    return {
        'last_seen_at': stage.last_seen_at.isoformat(),
        'days': days,
        'message': message,
    }


# ══════════════════════════════════════════════════════════════
# T3 · 复盘（唯一大量写库的阶段，写完后只读）
# ══════════════════════════════════════════════════════════════

def _nearest_previous_period_key(stage, period_type):
    """给「补归档」用：返回 `stage` 下**最近一个还没归档**的周期 key（若在追补）。"""
    today = timezone.localdate()
    start, end, key = period_range(period_type, today)
    # 若当前周期还没结束（今天就在周期内），则上一个周期的 key 才算「该归档了」
    if period_type == 'weekly':
        prev_ref = start - dt.timedelta(days=1)
    else:
        prev_ref = start - dt.timedelta(days=1)
    _, _, prev_key = period_range(period_type, prev_ref)
    return prev_key


@transaction.atomic
def close_period(period_type, period_key, skipped_metric_ids=None, answer_sheet=None):
    """归档 = 定格（设计稿 §5.1 事务里的六件事）。

    🔴 **系统不自动归档** —— 归不归档、什么时候归档是**你的动作**（V3）。
    🔴 已归档的周期再次归档 ⇒ **409**（不静默覆盖）。
    """
    stage = get_open_stage()
    if stage is None:
        raise SelfRunError('当前没有进行中的阶段。')

    start, end = parse_period_key(period_type, period_key)
    obj = SelfRunPeriod.objects.filter(
        stage=stage, period_type=period_type, period_key=period_key,
    ).first()
    if obj is not None and obj.closed_at is not None:
        raise ConflictError(f'{period_key} 已经归档过了。')

    skipped = list(skipped_metric_ids or [])
    metrics = [m for m in stage.metrics.filter(status='active') if m.period_type == period_type]
    plans_map = _plans_by_metric([m.id for m in metrics])
    targets = {
        m.id: resolve_targets(m, period_key, plans_map.get(m.id) or [])
        for m in metrics
    }
    readings = [
        compute_metric_reading(
            m, start, end, skipped=m.id in skipped,
            period_key=period_key, plans=plans_map.get(m.id) or [],
        )
        for m in metrics
    ]

    now = timezone.now()
    # 判定：周按达标率；月按三问（未答则留空，等答题时重判）
    if period_type == 'monthly':
        status = compute_monthly_status(answer_sheet)
    else:
        status = compute_period_status(stage, readings)

    # 补归档留痕：距周期结束超过 7 天 ⇒ 显式标注「此数事后补算」
    over = (now.date() - end).days
    is_backfilled = over > BACKFILL_WARN_DAYS

    if obj is None:
        obj = SelfRunPeriod(stage=stage, period_type=period_type, period_key=period_key)
    obj.period_start = start
    obj.period_end = end
    obj.is_partial = start < stage.start_date
    obj.status = status
    obj.readings = readings
    # 🔴 指纹算的是**这一期生效**的目标值（按期修订过 ⇒ 两期本来就不是同一把尺子）。
    #    仍用 Decimal 原值拼串（不用 float），否则「12.00」与「12.0」会把指纹改掉。
    obj.config_fingerprint = config_fingerprint(
        stage, resolved={mid: (t[0], t[1]) for mid, t in targets.items()},
    )
    obj.skipped_metric_ids = skipped
    if answer_sheet:
        obj.answer_sheet = answer_sheet
    obj.closed_at = now
    obj.is_backfilled = is_backfilled
    obj.backfilled_at = now if is_backfilled else None
    obj.save()
    return obj, {'backfill_days': over if is_backfilled else 0}


@transaction.atomic
def update_review(period, review_text=None, answer_sheet=None):
    """归档后**仍可写**的两项：你写的字（记忆型 ≠ 数据型）。

    🔴 每次补写留 `at` ⇒ 界面上标「补写于归档后 N 天」——
       「当时的想法」和「事后的解释」不能混在一起。
    """
    written = []
    if review_text is not None and review_text != period.review_text:
        edits = list(period.review_edits or [])
        if period.closed_at is not None:
            days = (timezone.localdate() - timezone.localtime(period.closed_at).date()).days
            edits.append({
                'text': period.review_text or '',
                'at': timezone.now().isoformat(),
                'days_after_close': days,
            })
        period.review_edits = edits
        period.review_text = review_text
        written.append('review_text')
    if answer_sheet is not None:
        period.answer_sheet = answer_sheet
        # 月度判定在答题这刻由三问**重判**（设计稿 §2.5 的「10-31 填三问」那一步）
        if period.period_type == 'monthly':
            new_status = compute_monthly_status(answer_sheet)
            if new_status:
                period.status = new_status
        written.append('answer_sheet')
    if written:
        period.save()
    return period, written


def reopen_period(period, reason):
    """重开（改历史判定的**唯一出口**，且留痕）。

    ⚠️ 限**最近一期**，且要求阶段仍在进行中 —— 否则就是「改写历史」。
    """
    if period.closed_at is None:
        raise SelfRunError('这一期还没归档，不需要重开。')
    if not reason:
        raise SelfRunError('重开必须写原因。')
    stage = period.stage
    latest = stage.periods.filter(
        period_type=period.period_type, closed_at__isnull=False,
    ).order_by('-period_start').first()
    if latest is None or latest.id != period.id:
        raise SelfRunError('只允许重开最近一期（更早的属于「改写历史」）。')
    if stage.status not in OPEN_STAGE_STATUSES:
        raise SelfRunError('阶段已收尾，不能再重开周期。')
    period.closed_at = None
    period.reopen_count = (period.reopen_count or 0) + 1
    period.reopened_at = timezone.now()
    period.reopen_reason = reason
    period.save()
    return period


# ══════════════════════════════════════════════════════════════
# T4 · 事后分析（几乎不写库，唯一例外是阶段总结）
# ══════════════════════════════════════════════════════════════

def compute_stage_summary(stage):
    """阶段总结的**数字部分**（实时算，不落库）。

    🔴 只有「你写的那段话」落库（`save_summary`），数字永远现算 ——
       因为改口径后数字应该跟着变；而你写话时**看到的那个数**会另存进 `summary_snapshot`。
    """
    periods = list(stage.periods.filter(closed_at__isnull=False).order_by('period_start'))
    weekly = [p for p in periods if p.period_type == 'weekly']
    monthly = [p for p in periods if p.period_type == 'monthly']
    counted_weeks = [p for p in weekly if not p.is_partial]   # 残缺周不进阶段达标率

    metrics = list(stage.metrics.all())
    plans_map = _plans_by_metric([m.id for m in metrics])
    per_metric = []
    for m in metrics:
        pool = weekly if m.period_type == 'weekly' else monthly
        values, hits = [], 0
        best = None
        for p in pool:
            for r in (p.readings or []):
                if r.get('metric_id') != m.id or r.get('skipped'):
                    continue
                if r.get('verdict') == 'unknown':
                    continue
                v = r.get('final_value')
                if v is None:
                    continue
                values.append(v)
                if r.get('verdict') in ('goal', 'floor'):
                    hits += 1
                if best is None or v > best['value']:
                    best = {'value': v, 'period_key': p.period_key}
        plans = plans_map.get(m.id) or []
        per_metric.append({
            'metric_id': m.id,
            'name': m.name,
            'unit': m.unit,
            'period_type': m.period_type,
            # ⚠️ 这里是**阶段默认**的双档（`Metric` 上的值）。
            #    按期改过的期，其真实目标在各自的 `readings` 里（冻结过）——
            #    `plan_periods` 用来提示「这条换过尺子，别拿默认值去读往期」。
            'goal_value': _f(m.goal_value),
            'floor_value': _f(m.floor_value),
            'plan_count': len(plans),
            'plan_periods': sorted({p.period_key for p in plans}),
            'avg': round(sum(values) / len(values), 2) if values else None,
            'hit': hits,
            'total': len(values),
            'best': best,
        })

    breakdown = {
        'period_type': 'weekly',
        'on_track': sum(1 for p in counted_weeks if p.status == 'on_track'),
        'slipping': sum(1 for p in counted_weeks if p.status == 'slipping'),
        'slid': sum(1 for p in counted_weeks if p.status == 'slid'),
        'fallow': sum(1 for p in counted_weeks if p.status == 'fallow'),
    }

    return {
        'stage_id': stage.id,
        'name': stage.name,
        'start_date': str(stage.start_date),
        'end_date': str(stage.end_date) if stage.end_date else None,
        'total_weeks': len(weekly),
        'counted_weeks': len(counted_weeks),
        'partial_weeks': len(weekly) - len(counted_weeks),
        'total_months': len(monthly),
        'metrics': per_metric,
        'weekly_breakdown': breakdown,
        'monthly_statuses': [
            {'period_key': p.period_key, 'status': p.status,
             'yes_count': _monthly_yes_count(p.answer_sheet)}
            for p in monthly
        ],
        # 指纹分组：这一阶段用过几把尺子（T4「尺子断点」的骨架）
        'fingerprints': _fingerprint_groups(periods),
    }


def _monthly_yes_count(answer_sheet):
    if not answer_sheet:
        return None
    return sum(
        1 for k in ('q1_income', 'q2_output', 'q3_runway')
        if (answer_sheet.get(k) or {}).get('answer') is True
    )


def _fingerprint_groups(periods):
    """按 `config_fingerprint` 把周期分组 —— 同组才可直接比（T4 指纹闸门）。"""
    groups = []
    for p in periods:
        fp = p.config_fingerprint or ''
        if groups and groups[-1]['fingerprint'] == fp:
            groups[-1]['periods'].append(p.period_key)
        else:
            groups.append({'fingerprint': fp, 'periods': [p.period_key]})
    return groups


@transaction.atomic
def save_summary(stage, text):
    """写阶段总结 —— **T4 唯一落库的分析**。

    🔴 同时冻结 `summary_snapshot`（**你写这段话时看到的数**）：
       将来口径变了重算会不同，而你当时是看着那个数写下这段话的；
       不冻结 ⇔ 你留下的文字会与旁边的数字对不上，且你不知道是哪个变了。
    """
    snapshot = compute_stage_summary(stage)
    stage.summary = text or ''
    stage.summary_snapshot = snapshot
    stage.summary_at = timezone.now()
    stage.save(update_fields=['summary', 'summary_snapshot', 'summary_at', 'updated_at'])
    return stage, snapshot


@transaction.atomic
def close_stage(stage, end_date=None):
    """收尾阶段：写 `end_date` + `status='closed'`。"""
    if stage.status == 'closed':
        raise SelfRunError('这个阶段已经收尾了。')
    if not (stage.summary or '').strip():
        raise SelfRunError('收尾前请先写下阶段总结（哪怕一句话）。')
    stage.end_date = end_date or timezone.localdate()
    stage.status = 'closed'
    stage.save(update_fields=['end_date', 'status', 'updated_at'])
    return stage


@transaction.atomic
def copy_stage(from_stage, name, start_date):
    """用这个配置开新阶段。

    | 复制 | 不复制 | 必然不同 |
    |---|---|---|
    | `active` 的 `Metric`（含 `source_config` / 双档 / `why`） | `Period`（历史结论**永远跟着原阶段**） | `config_fingerprint`（新 `stage.id`） |
    | `template_key`（来源可追溯） | `Checkin`（明细不跟） | 🔴 **目标值必须重设**（阶段变了，KPI 可能不同） |

    🔴 必须在界面上显式说「目标值仍是上一阶段的，请逐条重设」——
       否则改过目标值之后你会以为「我变差了」，**实际是尺子换了**（V2）。
    """
    if not name or not name.strip():
        raise SelfRunError('新阶段名称不能为空。')
    if SelfRunStage.objects.filter(status__in=OPEN_STAGE_STATUSES).exists():
        raise SelfRunError('已有进行中的阶段，请先收尾它。')

    stage = SelfRunStage.objects.create(
        name=name.strip(), start_date=start_date or timezone.localdate(),
        status='active', note=f'复制自「{from_stage.name}」',
    )
    created = []
    for m in from_stage.metrics.filter(status='active').order_by('sort_order', 'id'):
        new = SelfRunMetric.objects.create(
            stage=stage, template_key=m.template_key, name=m.name,
            period_type=m.period_type, unit=m.unit, direction=m.direction,
            goal_value=m.goal_value, floor_value=m.floor_value,
            goal_why=m.goal_why, floor_why=m.floor_why,
            agg=m.agg, source_kind=m.source_kind, source_config=m.source_config,
            status='active', sort_order=m.sort_order,
        )
        SelfRunMetricLog.objects.create(
            metric=new, action='created',
            reason_note=f'复制自阶段 #{from_stage.id}「{from_stage.name}」',
            to_value={'copied_from_metric_id': m.id},
        )
        created.append(new)
    return stage, created
